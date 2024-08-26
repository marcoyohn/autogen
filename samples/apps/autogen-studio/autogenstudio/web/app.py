import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
from mimetypes import guess_type
import os
import queue
import threading
import time
import traceback
from contextlib import asynccontextmanager
from typing import Annotated, Any, Optional
from urllib.parse import quote
import uuid

from fastapi import FastAPI, File, Form, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.requests import HTTPConnection
from fastapi.responses import PlainTextResponse, RedirectResponse, StreamingResponse, Response as OkResponse
from fastapi.staticfiles import StaticFiles
import jwt
from loguru import logger
from openai import OpenAIError

from autogen.function_utils import serialize_to_str
from autogen.oss.Osss import OssConfig, Osss, OsssConfig

from ..chatmanager import AutoGenChatManager, WebSocketConnectionManager
from ..database import workflow_from_id
from ..database.dbmanager import DBManager
from ..datamodel import Agent, Message, Model, OssFile, Response, Session, Skill, Workflow
from ..utils import check_and_cast_datetime_fields, init_app_folders, md5_hash, test_model
from ..version import VERSION

from ..utils.auth_middleware import *
from ..utils.uc import *
from ..utils.user_message import *
from ..oss.db_oss_config import *
from starlette.authentication import requires
from starlette.requests import Request

thread_pool= ThreadPoolExecutor(max_workers=200)
thread_pool_agent= ThreadPoolExecutor(max_workers=200)

managers = {"chat": None}  # manage calls to autogen
# Create thread-safe queue for messages between api thread and autogen threads
message_queue = queue.Queue()
job_done = object()  # signals the processing is done
active_connections = []
active_connections_lock = asyncio.Lock()
websocket_manager = WebSocketConnectionManager(
    active_connections=active_connections,
    active_connections_lock=active_connections_lock,
)


def message_handler():
    while True:
        message = message_queue.get()
        logger.info(
            "** Processing Agent Message on Queue: Active Connections: "
            + str([client_id for _, client_id in websocket_manager.active_connections])
            + " **"
        )
        for connection, socket_client_id in websocket_manager.active_connections:
            if message["connection_id"] == socket_client_id:
                logger.info(
                    f"Sending message to connection_id: {message['connection_id']}. Connection ID: {socket_client_id}"
                )
                # TODO 是否需要转换image_url的oss格式为url格式? 还是调用方自行转换
                asyncio.run(websocket_manager.send_message(message, connection))
            else:
                logger.info(
                    f"Skipping message for connection_id: {message['connection_id']}. Connection ID: {socket_client_id}"
                )
        message_queue.task_done()


message_handler_thread = threading.Thread(target=message_handler, daemon=True)
message_handler_thread.start()


app_file_path = os.path.dirname(os.path.abspath(__file__))
folders = init_app_folders(app_file_path)
ui_folder_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui")

database_engine_uri = folders["database_engine_uri"]
dbmanager = DBManager(engine_uri=database_engine_uri)


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("***** App started *****")
    managers["chat"] = AutoGenChatManager(message_queue=message_queue)
    if not os.environ.get("UC_APP_CODE", None):
        # 本地部署
        dbmanager.create_db_and_tables()

    # add by ymc 
    oss_list_config = os.environ.get("OSS_LIST", None)
    if oss_list_config:
        # [{"app_id":"10523", "base_url":"https://cstore.test.seewo.com", "key_prefix":"she-agent/", "oss_type":"cstore", "is_default":true},{"app_id":"10410", "base_url":"https://cstore.test.seewo.com", "key_prefix":"she-models/", "oss_type":"cstore", "is_default":false}]
        oss_list_config = json.loads(oss_list_config)
        oss_list = []
        for oss_config in oss_list_config:
            if oss_config["oss_type"] == "db_oss":
                oss_list.append(DbOssConfig(**oss_config)) 
            else:
                oss_list.append(OssConfig(**oss_config))        
        osss_config = OsssConfig(oss_list=oss_list)
        Osss.buildDefault(osss_config)
    else:
        raise RuntimeError("请配置OSS_LIST")

    yield
    # Close all active connections
    await websocket_manager.disconnect_all()
    print("***** App stopped *****")


app = FastAPI(lifespan=lifespan)


# allow cross origin requests for testing on localhost:800* ports only
app.add_middleware(
    CORSMiddleware,
    allow_origins=[        
        "none:http://localhost:8000",
    ],
    allow_origin_regex = r"(http|https)://(.+\.seewo\.com|.+\.cvte\.com|localhost|127\.0\.0\.1)(:\d+|)",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


api = FastAPI(root_path="/api")

def auth_error_handler(conn: HTTPConnection, exc: Exception) -> Response:
    return PlainTextResponse(str(exc), status_code=401)

api.add_middleware(AuthMiddleware, verify_func=verify_authorization, auth_error_handler=auth_error_handler, excluded_urls=["/api/version", "/api/docs", "/api/openapi.json", "/api/db-oss/upload", "/api/db-oss/download", "/api/db-oss/internal-upload", "/api/db-oss/internal-download"])
# mount an api route such that the main route serves the ui and the /api
app.mount("/api", api)

app.mount("/", StaticFiles(directory=ui_folder_path, html=True), name="ui")
api.mount(
    "/files",
    StaticFiles(directory=folders["files_static_root"], html=True),
    name="files",
)


# manage websocket connections

def create_entity(model: Any, model_class: Any, filters: dict = None):
    """Create a new entity"""
    model = check_and_cast_datetime_fields(model)
    try:
        response: Response = dbmanager.upsert(model)
        return response.model_dump(mode="json")

    except Exception as ex_error:
        print(ex_error)
        return {
            "status": False,
            "message": f"Error occurred while creating {model_class.__name__}: " + str(ex_error),
        }


def list_entity(
    model_class: Any,
    filters: dict = None,
    return_json: bool = True,
    order: str = "desc",
):
    """List all entities for a user"""
    return dbmanager.get(model_class, filters=filters, return_json=return_json, order=order)


def delete_entity(model_class: Any, filters: dict = None):
    """Delete an entity"""

    return dbmanager.delete(filters=filters, model_class=model_class)


@api.get("/skills")
async def list_skills():
    """List all skills for a user"""
    return list_entity(Skill, filters=None)

@api.post("/skills")
@requires("admin") 
async def create_skill(skill: Skill, request: Request):
    """Create a new skill"""
    filters = {"user_id": request.user.identity}
    return create_entity(skill, Skill, filters=filters)


@api.delete("/skills/delete")
@requires("admin") 
async def delete_skill(skill_id: int, request: Request):
    """Delete a skill"""
    filters = {"id": skill_id}
    return delete_entity(Skill, filters=filters)


@api.get("/models")
async def list_models(request: Request):
    """List all models for a user"""
    if 'admin' in request.auth.scopes:
        return list_entity(Model, filters=None)
    else:
        models = list_entity(Model, filters=None)
        if models and models.data:
            for model in models.data:
                if model.get("api_key"):
                    model["api_key"] = "..."    

        return models


@api.post("/models")
@requires("admin") 
async def create_model(model: Model, request: Request):
    """Create a new model"""
    return create_entity(model, Model)


@api.post("/models/test")
async def test_model_endpoint(model: Model):
    """Test a model"""
    try:
        response = test_model(model)
        return {
            "status": True,
            "message": "Model tested successfully",
            "data": response,
        }
    except (OpenAIError, Exception) as ex_error:
        return {
            "status": False,
            "message": "Error occurred while testing model: " + str(ex_error),
        }


@api.delete("/models/delete")
@requires("admin") 
async def delete_model(model_id: int, request: Request):
    """Delete a model"""
    filters = {"id": model_id}
    return delete_entity(Model, filters=filters)


@api.get("/agents")
async def list_agents():
    """List all agents for a user"""
    return list_entity(Agent, filters=None)


@api.post("/agents")
@requires("admin") 
async def create_agent(agent: Agent, request: Request):
    """Create a new agent"""
    return create_entity(agent, Agent)


@api.delete("/agents/delete")
@requires("admin") 
async def delete_agent(agent_id: int, request: Request):
    """Delete an agent"""
    filters = {"id": agent_id}
    return delete_entity(Agent, filters=filters)


@api.post("/agents/link/model/{agent_id}/{model_id}")
@requires("admin") 
async def link_agent_model(agent_id: int, model_id: int, request: Request):
    """Link a model to an agent"""
    return dbmanager.link(link_type="agent_model", primary_id=agent_id, secondary_id=model_id)


@api.delete("/agents/link/model/{agent_id}/{model_id}")
@requires("admin") 
async def unlink_agent_model(agent_id: int, model_id: int, request: Request):
    """Unlink a model from an agent"""
    return dbmanager.unlink(link_type="agent_model", primary_id=agent_id, secondary_id=model_id)


@api.get("/agents/link/model/{agent_id}")
async def get_agent_models(agent_id: int, request: Request):
    """Get all models linked to an agent"""
    if 'admin' in request.auth.scopes:
        return dbmanager.get_linked_entities("agent_model", agent_id, return_json=True)
    else:
        models = dbmanager.get_linked_entities("agent_model", agent_id, return_json=True)
        if models and models.data:
            for model in models.data:
                if model.get("api_key"):
                    model["api_key"] = "..."    

        return models    


@api.post("/agents/link/skill/{agent_id}/{skill_id}")
@requires("admin") 
async def link_agent_skill(agent_id: int, skill_id: int, request: Request):
    """Link an a skill to an agent"""
    return dbmanager.link(link_type="agent_skill", primary_id=agent_id, secondary_id=skill_id)


@api.delete("/agents/link/skill/{agent_id}/{skill_id}")
@requires("admin") 
async def unlink_agent_skill(agent_id: int, skill_id: int, request: Request):
    """Unlink an a skill from an agent"""
    return dbmanager.unlink(link_type="agent_skill", primary_id=agent_id, secondary_id=skill_id)


@api.get("/agents/link/skill/{agent_id}")
async def get_agent_skills(agent_id: int):
    """Get all skills linked to an agent"""
    return dbmanager.get_linked_entities("agent_skill", agent_id, return_json=True)


@api.post("/agents/link/agent/{primary_agent_id}/{secondary_agent_id}")
@requires("admin") 
async def link_agent_agent(primary_agent_id: int, secondary_agent_id: int, request: Request):
    """Link an agent to another agent"""
    return dbmanager.link(
        link_type="agent_agent",
        primary_id=primary_agent_id,
        secondary_id=secondary_agent_id,
    )


@api.delete("/agents/link/agent/{primary_agent_id}/{secondary_agent_id}")
@requires("admin") 
async def unlink_agent_agent(primary_agent_id: int, secondary_agent_id: int, request: Request):
    """Unlink an agent from another agent"""
    return dbmanager.unlink(
        link_type="agent_agent",
        primary_id=primary_agent_id,
        secondary_id=secondary_agent_id,
    )


@api.get("/agents/link/agent/{agent_id}")
async def get_linked_agents(agent_id: int):
    """Get all agents linked to an agent"""
    return dbmanager.get_linked_entities("agent_agent", agent_id, return_json=True)


@api.get("/workflows")
async def list_workflows(name: str=None):
    """List all workflows for a user"""
    filters = {"name": name} if name else None
    return list_entity(Workflow, filters=filters)


@api.get("/workflows/{workflow_id}")
async def get_workflow(workflow_id: int):
    """Get a workflow"""
    filters = {"id": workflow_id}
    return list_entity(Workflow, filters=filters)

@api.post("/workflows/{workflow_id}/run")
async def run_workflow(message: Message, workflow_id: int, request: Request=None):
    if message.session_id:
        raise RuntimeError("message with session id, will be call /sessions/{session_id}/workflow/{workflow_id}/run")
    if request:
        message.user_id = request.user.identity
    # add by ymc : add context
    context: Dict[str, Any] = {"user_id": request.user.identity}
    return await asyncio.to_thread(block_run_session_workflow, context=context, message=message, session_id=None, workflow_id=workflow_id)

@api.post("/workflows/{workflow_id}/run/sse")
async def run_workflow_sse(message: Message, workflow_id: int, request: Request=None):
    if message.session_id:
        raise RuntimeError("message with session id, will be call /sessions/{session_id}/workflow/{workflow_id}/run/sse")
    if request:
        message.user_id = request.user.identity
    sse_queue = queue.Queue()
    # add by ymc : add context
    context: Dict[str, Any] = {"user_id": request.user.identity}
    thread_pool.submit(block_run_session_workflow, context=context, message=message, session_id=None, workflow_id=workflow_id, notify_message_queue=sse_queue, need_notify_job_done=True)

    return StreamingResponse(
        adapter_queue(sse_queue),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )

@api.post("/workflows")
@requires("admin") 
async def create_workflow(workflow: Workflow, request: Request):
    """Create a new workflow"""
    return create_entity(workflow, Workflow)


@api.delete("/workflows/delete")
@requires("admin") 
async def delete_workflow(workflow_id: int, request: Request):
    """Delete a workflow"""
    filters = {"id": workflow_id}
    return delete_entity(Workflow, filters=filters)


@api.post("/workflows/link/agent/{workflow_id}/{agent_id}/{agent_type}")
@requires("admin") 
async def link_workflow_agent(workflow_id: int, agent_id: int, agent_type: str, request: Request):
    """Link an agent to a workflow"""
    return dbmanager.link(
        link_type="workflow_agent",
        primary_id=workflow_id,
        secondary_id=agent_id,
        agent_type=agent_type,
    )


@api.delete("/workflows/link/agent/{workflow_id}/{agent_id}/{agent_type}")
@requires("admin") 
async def unlink_workflow_agent(workflow_id: int, agent_id: int, agent_type: str, request: Request):
    """Unlink an agent from a workflow"""
    return dbmanager.unlink(
        link_type="workflow_agent",
        primary_id=workflow_id,
        secondary_id=agent_id,
        agent_type=agent_type,
    )


@api.get("/workflows/link/agent/{workflow_id}/{agent_type}")
async def get_linked_workflow_agents(workflow_id: int, agent_type: str):
    """Get all agents linked to a workflow"""
    return dbmanager.get_linked_entities(
        link_type="workflow_agent",
        primary_id=workflow_id,
        agent_type=agent_type,
        return_json=True,
    )


@api.get("/sessions")
async def list_sessions(request: Request, workflow_id: int=None, name: str=None):
    """List all sessions for a user"""
    filters = {"user_id": request.user.identity}
    if workflow_id:
        filters["workflow_id"] = workflow_id
    if name:
        filters["name"] = name
    return list_entity(Session, filters=filters)


@api.post("/sessions")
async def create_session(session: Session, request: Request):
    """Create a new session"""
    session.user_id = request.user.identity
    return create_entity(session, Session)


@api.delete("/sessions/delete")
@requires("admin") 
async def delete_session(session_id: int, request: Request):
    """Delete a session"""
    filters = {"id": session_id, "user_id": request.user.identity}
    return delete_entity(Session, filters=filters)


@api.get("/sessions/{session_id}/messages")
async def list_messages(session_id: int, request: Request):
    """List all messages for a use session"""
    filters = {"user_id": request.user.identity, "session_id": session_id}
    return list_entity(Message, filters=filters, order="asc", return_json=True)


@api.post("/sessions/{session_id}/workflow/{workflow_id}/run")
async def run_session_workflow(message: Message, session_id: int, workflow_id: int, request: Request=None):
    if request:
        message.user_id = request.user.identity
    message.session_id = session_id
    # add by ymc : add context
    context: Dict[str, Any] = {"user_id": request.user.identity}
    return await asyncio.to_thread(block_run_session_workflow, context=context, message=message, session_id=session_id, workflow_id=workflow_id)

@api.post("/sessions/{session_id}/workflow/{workflow_id}/run/sse")
async def run_session_workflow_sse(message: Message, session_id: int, workflow_id: int, request: Request=None):
    if request:
        message.user_id = request.user.identity
    message.session_id = session_id

    sse_queue = queue.Queue()
    # add by ymc : add context
    context: Dict[str, Any] = {"user_id": request.user.identity}
    thread_pool.submit(block_run_session_workflow, context=context, message=message, session_id=session_id, workflow_id=workflow_id, notify_message_queue=sse_queue, need_notify_job_done=True)

    return StreamingResponse(
        adapter_queue(sse_queue),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )

# add by ymc
def adapter_queue(queue: queue.Queue):
    while True:
        next_item = queue.get(block=True)  # blocks until an input is available
        if next_item is job_done:
            break
        # TODO 是否需要转换image_url的oss格式为url格式? 还是调用方自行转换
        yield f"data: {serialize_to_str(next_item)}\n\n"

def block_run_session_workflow(context: Dict[str, Any], message: Message, session_id: int, workflow_id: int, notify_message_queue: Optional[queue.Queue]=None, need_notify_job_done: bool = False):
    """Runs a workflow on provided message"""
    # add by ymc: send message to queue
    def send_message(message: str) -> None:    
        if notify_message_queue: 
            notify_message_queue.put(message, block=True)  
    try:
        if message.role is None or message.role == "":
            raise RuntimeError("role 不能为空")
        # add by ymc : 转换url为oss格式
        ensure_user_image_oss(message.content, context)

        # add by ymc: 没有则生成connection_id，便于关联请求和响应
        if message.connection_id is None:
            message.connection_id = str(uuid.uuid4())

        message_dict = message.model_dump()

        user_message_history = (
            dbmanager.get(
                Message,
                filters={"user_id": message.user_id, "session_id": message.session_id},
                return_json=True,
            ).data
            if session_id is not None
            else []
        )
        # add by ymc: filter user_history
        filter_user_history = []
        pre_item = message_dict
        count = 0
        for item in user_message_history[::-1]:
            # 截断：超过10消息，并保证消息以user开头
            if count > 10 and pre_item["role"] == "user":
                break
            if ("function_call" in item and item["function_call"]) or ("tool_calls" in item and item["tool_calls"]):  
                #下一个消息不是tool_responses/function response时，截断
                if not (pre_item and (("tool_responses" in pre_item and pre_item["tool_responses"]) or ("role" in pre_item and pre_item["role"] == "function"))):
                    break            
            filter_user_history.insert(0, item)
            pre_item = item
            count += 1
        user_message_history = filter_user_history

        # save incoming message
        dbmanager.upsert(message)
        user_dir = os.path.join(folders["files_static_root"], "user", md5_hash(message.user_id))
        os.makedirs(user_dir, exist_ok=True)
        workflow = workflow_from_id(workflow_id, dbmanager=dbmanager)
        agent_response: Message = managers["chat"].chat(
            message=message,
            history=user_message_history,
            user_dir=user_dir,
            workflow=workflow,
            connection_id=message.connection_id,
            send_message_function=send_message, # add by ymc
            context=context,
        )

        response: Response = dbmanager.upsert(agent_response)

        response_socket_message = {
            "type": "agent_response",
            "data": response.model_dump(mode="json"),
            "connection_id": message.connection_id,
        }
        if notify_message_queue: 
            notify_message_queue.put(response_socket_message, block=True) 
            if need_notify_job_done: 
                notify_message_queue.put(job_done, block=True)
        return response
    except Exception as ex_error:
        print(traceback.format_exc())
        # modify by ymc
        response = {
                            "status": False,
                            "message": "Error occurred while processing message: " + str(ex_error),
                        }
        if notify_message_queue: 
            response_socket_message = {
                "type": "agent_response",
                "data": serialize_to_str(response),
                "connection_id": message.connection_id,
            }            
            notify_message_queue.put(response_socket_message, block=True) 
            if need_notify_job_done: 
                notify_message_queue.put(job_done, block=True)      
        return response


@api.get("/version")
async def get_version():
    return {
        "status": True,
        "message": "Version retrieved successfully",
        "data": {"version": VERSION},
    }


# websockets


async def process_socket_message(data: dict, websocket: WebSocket, client_id: str, user_id: str):
    print(f"Client says: {data['type']}")
    if data["type"] == "user_message":
        user_message = Message(**data["data"])
        user_message.user_id = user_id
        session_id = data["data"].get("session_id", None)
        workflow_id = data["data"].get("workflow_id", None)    
        # add by ymc : add context
        context: Dict[str, Any] = {"user_id": user_id}
        # modify by ymc: 修改为调用内部方法 
        await asyncio.to_thread(block_run_session_workflow, context=context, message=user_message, session_id=session_id, workflow_id=workflow_id, notify_message_queue=message_queue)        


@api.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await websocket_manager.connect(websocket, client_id)
    try:
        while True:
            data = await websocket.receive_json()
            await process_socket_message(data, websocket, client_id, websocket.user.identity)
    except WebSocketDisconnect:
        print(f"Client #{client_id} is disconnected")
        await websocket_manager.disconnect(websocket)

# add by ymc
@api.get("/current-user")
async def current_user(request: Request):
    """current user"""
    return request.user

# add by ymc
@api.get("/ws-token")
async def ws_token(request: Request):
    """get ws token, jwt format"""
    payload = {"user": {key: value for key, value in request.user.__dict__.items() if not key.startswith('__')}, "scopes": request.auth.scopes, 'exp': int(time.time()) + 300}
    return "jwt:" + jwt.encode(payload, os.environ["WS_TOKEN_JWT_SECRET"], algorithm=os.environ["WS_TOKEN_JWT_ALGORITHM"])

# add by ymc
@api.get("/osss/request-upload-url")
async def request_oss_upload_url(request: Request, file_name: str):
    if "@" in file_name:
        raise RuntimeError("文件名不能包含@特殊字符")
    
    oss = Osss.default().defaultOss()
    policy = await oss.async_get_upload_policy()
    file_key=f"{oss.key_prefix}{str(uuid.uuid4())}/{quote(file_name)}"
    ret: Dict[str, Any] = {"upload_url": policy.upload_url, "method": policy.method, "oss_key": f"{file_key}@{oss.app_id}"}
    ret["form_fields"] = {**policy.form_fields, "key": file_key}
    ret["header_fields"] = {**policy.header_fields}

    return {
        "status": True,
        "message": "successfully",
        "data": ret,
    }

# add by ymc
@api.get("/osss/request-download-url")
async def request_oss_download_url(request: Request, oss_key: str, expire_seconds: Optional[int]=None):
    file_key, app_id = oss_key.split("@")
    oss = Osss.default().getOss(app_id)
    if oss is None:
        raise RuntimeError("不支持的oss_key")
    
    return {
        "status": True,
        "message": "successfully",
        "data": await oss.async_get_download_url(file_key, expire_seconds or 3600),
    }

# add by ymc
@api.get("/osss/redirect-download")
async def redirect_download_oss_file(request: Request, oss_key: str, expire_seconds: Optional[int]=None):
    file_key, app_id = oss_key.split("@")
    oss = Osss.default().getOss(app_id)
    if oss is None:
        raise RuntimeError("不支持的oss_key")
    download_url = await oss.async_get_download_url(file_key, expire_seconds or 3600)
    return RedirectResponse(download_url)
    

@api.post("/db-oss/upload")
async def db_oss_upload(file: Annotated[bytes, File()],
                        key: Annotated[str, Form()], 
                        app_id: Annotated[str, Form()], 
                        sign: Annotated[str, Form()]):
    payload = jwt.decode(sign, os.environ["WS_TOKEN_JWT_SECRET"], algorithms=[os.environ["WS_TOKEN_JWT_ALGORITHM"]])
    exp = int(payload["exp"])
    if time.time() > exp:
        raise RuntimeError("token效验异常！")
    if not (payload["op"] == "upload" and payload["app_id"] == app_id):
        raise RuntimeError(f"效验不通过！")
    await do_db_oss_upload(key, app_id, file)
    return OkResponse()
    

@api.post("/db-oss/internal-upload")
async def db_oss_internal_upload(file: Annotated[bytes, File()],                                 
                                 key: Annotated[str, Form()], 
                                 app_id: Annotated[str, Form()], 
                                 sign: Annotated[str, Form()]):
    payload = jwt.decode(sign, os.environ["WS_TOKEN_JWT_SECRET"], algorithms=[os.environ["WS_TOKEN_JWT_ALGORITHM"]])
    exp = int(payload["exp"])
    if time.time() > exp:
        raise RuntimeError("token效验异常！")
    if not (payload["op"] == "internal_upload" and payload["app_id"] == app_id):
        raise RuntimeError(f"效验不通过！")
    # file_bytes = await fileb.read()
    await do_db_oss_upload(key, app_id, file)
    return OkResponse()
    

@api.get("/db-oss/download")
async def db_oss_download(request: Request, key: str, app_id: str, sign: str):
    payload = jwt.decode(sign, os.environ["WS_TOKEN_JWT_SECRET"], algorithms=[os.environ["WS_TOKEN_JWT_ALGORITHM"]])
    exp = int(payload["exp"])
    if time.time() > exp:
        raise RuntimeError("token效验异常！")
    if not (payload["op"] == "download" and payload["key"] == key and payload["app_id"] == app_id):
        raise RuntimeError(f"效验不通过！")
    return await do_db_oss_download(key, app_id)

@api.get("/db-oss/internal-download")
async def db_oss_internal_download(request: Request, key: str, app_id: str, sign: str):
    payload = jwt.decode(sign, os.environ["WS_TOKEN_JWT_SECRET"], algorithms=[os.environ["WS_TOKEN_JWT_ALGORITHM"]])
    exp = int(payload["exp"])
    if time.time() > exp:
        raise RuntimeError("token效验异常！")
    if not (payload["op"] == "internal_download" and payload["key"] == key and payload["app_id"] == app_id):
        raise RuntimeError(f"效验不通过！")
    return await do_db_oss_download(key, app_id)

async def do_db_oss_upload(key: str, app_id: str, file: bytes):
    # 根据key后缀名，匹配文件媒体类型
    media_type = guess_type(key)[0] or "text/plain"
    return await asyncio.to_thread(lambda key, app_id, file: dbmanager.upsert(OssFile(key=key, app_id=app_id, content=file, content_type=media_type)), key, app_id, file)

async def do_db_oss_download(key: str, app_id: str):
    filters = {"key": key, "app_id": app_id}    
    oss_files: Response[List[OssFile]] = await asyncio.to_thread(lambda filters: list_entity(OssFile, filters=filters), filters)
    if not oss_files.status:
        raise RuntimeError("系统异常")
    oss_files = oss_files.data
    if oss_files is None or len(oss_files) == 0:
        raise RuntimeError("文件不存在")
    oss_file = oss_files[0]
    # 根据媒体类型，设置不同的content-type，
    filename = key.split("/")[-1]
    content_disposition_filename = quote(filename)
    if content_disposition_filename != filename:
        content_disposition = "attachment; filename*=utf-8''{}".format(
            content_disposition_filename
        )
    else:
        content_disposition = 'attachment; filename="{}"'.format(
            filename
        )
    return OkResponse(content=oss_file["content"], headers={"content-disposition": content_disposition}, media_type=oss_file.get("content_type", None) or "application/octet-stream")