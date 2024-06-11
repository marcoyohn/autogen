from datetime import datetime
import inspect
import os
from os import path
from typing import Any, Callable, List, Optional, Protocol, Tuple, Type, Union, Dict, runtime_checkable

import autogen
from autogen.agentchat.agent import LLMAgent
from autogen.agentchat.chat import ChatResult
from autogen.agentchat.conversable_agent import ConversableAgent
from autogen.cache.abstract_cache_base import AbstractCache

from .datamodel import (
    Agent,
    AgentType,
    Message,
    SocketMessage,
)
from .utils import clear_folder, get_skills_from_prompt, load_code_execution_config, sanitize_model, load_plugins_module


class WorkflowManager:
    """
    AutoGenWorkFlowManager class to load agents from a provided configuration and run a chat between them
    """

    def __init__(
        self,
        workflow: Dict,
        history: Optional[List[Message]] = None,
        work_dir: str = None,
        clear_work_dir: bool = True,
        send_message_function: Optional[callable] = None,
        connection_id: Optional[str] = None,
    ) -> None:
        """
        Initializes the AutoGenFlow with agents specified in the config and optional
        message history.

        Args:
            config: The configuration settings for the sender and receiver agents.
            history: An optional list of previous messages to populate the agents' history.

        """
        # TODO - improved typing for workflow
        self.send_message_function = send_message_function
        self.connection_id = connection_id
        self.work_dir = work_dir or "work_dir"
        if clear_work_dir:
            clear_folder(self.work_dir)
        self.workflow = workflow
        self.sender = self.load(workflow.get("sender"))
        self.receiver = self.load(workflow.get("receiver"))
        self.agent_history = []

        if history:
            self._populate_history(history)

    def _serialize_agent(
        self,
        agent: Agent,
        mode: str = "python",
        include: Optional[List[str]] = {"config"},
        exclude: Optional[List[str]] = None,
    ) -> Dict:
        """ """
        # exclude = ["id","created_at", "updated_at","user_id","type"]
        exclude = exclude or {}
        include = include or {}
        if agent.type != AgentType.groupchat:
            exclude.update(
                {
                    "config": {
                        "admin_name",
                        "messages",
                        "max_round",
                        "admin_name",
                        "speaker_selection_method",
                        "allow_repeat_speaker",
                    }
                }
            )
        else:
            include = {
                "config": {
                    "admin_name",
                    "messages",
                    "max_round",
                    "admin_name",
                    "speaker_selection_method",
                    "allow_repeat_speaker",
                }
            }
        result = agent.model_dump(warnings=False, exclude=exclude, include=include, mode=mode)
        return result["config"]

    def process_message(
        self,
        sender: autogen.Agent,
        receiver: autogen.Agent,
        message: Dict,
        request_reply: bool = False,
        silent: bool = False,
        sender_type: str = "agent",
    ) -> None:
        """
        Processes the message and adds it to the agent history.

        Args:

            sender: The sender of the message.
            receiver: The receiver of the message.
            message: The message content.
            request_reply: If set to True, the message will be added to agent history.
            silent: determining verbosity.
            sender_type: The type of the sender of the message.
        """

        message = message if isinstance(message, dict) else {"content": message, "role": "user"}
        message_payload = {
            "recipient": receiver.name,
            "sender": sender.name,
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "sender_type": sender_type,
            "connection_id": self.connection_id,
            "message_type": "agent_message",
        }
        # if the agent will respond to the message, or the message is sent by a groupchat agent. This avoids adding groupchat broadcast messages to the history (which are sent with request_reply=False), or when agent populated from history
        if request_reply is not False or sender_type == "groupchat":
            self.agent_history.append(message_payload)  # add to history
            if self.send_message_function:  # send over the message queue
                socket_msg = SocketMessage(
                    type="agent_message",
                    data=message_payload,
                    connection_id=self.connection_id,
                )
                self.send_message_function(socket_msg.dict())

    def _populate_history(self, history: List[Message]) -> None:
        """
        Populates the agent message history from the provided list of messages.

        Args:
            history: A list of messages to populate the agents' history.
        """
        for msg in history:
            if isinstance(msg, dict):
                msg = Message(**msg)
            if msg.role == "user" or msg.role == "tool": # modify by ymc: 支持tool repsonses
                self.sender.send(
                    dict(vars(msg)), # modify by ymc: 支持function_call
                    self.receiver,
                    request_reply=False,
                    silent=True,
                )
            elif msg.role == "assistant":
                self.receiver.send(
                    dict(vars(msg)), # modify by ymc: 支持function_call
                    self.sender,
                    request_reply=False,
                    silent=True,
                )

    def sanitize_agent(self, agent: Dict) -> Agent:
        """ """

        skills = agent.get("skills", [])
        agent = Agent.model_validate(agent)
        agent.config.is_termination_msg = agent.config.is_termination_msg or (
            # modify by ymc，只处理content为str的场景
            lambda x: isinstance(x.get("content", ""), str) and "TERMINATE" in x.get("content", "").rstrip()[-20:]
        )

        def get_default_system_message(agent_type: str) -> str:
            if agent_type == "assistant":
                return autogen.AssistantAgent.DEFAULT_SYSTEM_MESSAGE
            else:
                return "You are a helpful AI Assistant."

        if agent.config.llm_config is not False:
            config_list = []
            for llm in agent.config.llm_config.config_list:
                # check if api_key is present either in llm or env variable
                if "api_key" not in llm and "OPENAI_API_KEY" not in os.environ:
                    error_message = f"api_key is not present in llm_config or OPENAI_API_KEY env variable for agent ** {agent.config.name}**. Update your workflow to provide an api_key to use the LLM."
                    raise ValueError(error_message)

                # only add key if value is not None
                sanitized_llm = sanitize_model(llm)
                config_list.append(sanitized_llm)
            agent.config.llm_config.config_list = config_list

        agent.config.code_execution_config = load_code_execution_config(
            agent.config.code_execution_config, work_dir=self.work_dir
        )

        if skills:
            skills_prompt = ""
            skills_prompt = get_skills_from_prompt(skills, self.work_dir)
            if agent.config.system_message:
                agent.config.system_message = agent.config.system_message + "\n\n" + skills_prompt
            else:
                agent.config.system_message = get_default_system_message(agent.type) + "\n\n" + skills_prompt
        return agent

    def load(self, agent: Any) -> autogen.Agent:
        """
        Loads an agent based on the provided agent specification.

        Args:
            agent_spec: The specification of the agent to be loaded.

        Returns:
            An instance of the loaded agent.
        """
        if not agent:
            raise ValueError(
                "An agent configuration in this workflow is empty. Please provide a valid agent configuration."
            )

        linked_agents = agent.get("agents", [])
        agent = self.sanitize_agent(agent)
        if agent.type == "groupchat":
            groupchat_agents = [self.load(agent) for agent in linked_agents]
            group_chat_config = self._serialize_agent(agent)
            group_chat_config["agents"] = groupchat_agents
            groupchat = autogen.GroupChat(**group_chat_config)
            agent = ExtendedGroupChatManager(
                groupchat=groupchat,
                message_processor=self.process_message,
                llm_config=agent.config.llm_config.model_dump(),
            )
            return agent

        else:
            if agent.type == "assistant":
                agent = ExtendedConversableAgent(
                    **self._serialize_agent(agent),
                    message_processor=self.process_message,
                )
            elif agent.type == "userproxy":
                agent = ExtendedConversableAgent(
                    **self._serialize_agent(agent),
                    message_processor=self.process_message,
                )
            # add by ymc
            elif agent.type == "custom":
                agent_type_names = agent.agent_type_name.split(".")
                agent_type = load_plugins_module(path.dirname(path.abspath(__file__)) + "/plugins", agent_type_names[0], agent_type_names[1])
                if "message_processor" in inspect.signature(agent_type.__init__).parameters:
                    delegate_agent = agent_type(**self._serialize_agent(agent), message_processor=self.process_message)
                else:
                    delegate_agent = agent_type(**self._serialize_agent(agent))
                agent = ExtendedProxyAgent(
                    delegate_agent=delegate_agent,
                    message_processor=self.process_message,
                )
            else:
                raise ValueError(f"Unknown agent type: {agent.type}")
            return agent


    # modify by ymc: message str修改为Union[str, Dict]
    def run(self, message: Union[str, Dict], clear_history: bool = False) -> None:
        """
        Initiates a chat between the sender and receiver agents with an initial message
        and an option to clear the history.

        Args:
            message: The initial message to start the chat.
            clear_history: If set to True, clears the chat history before initiating.
        """
        self.sender.initiate_chat(
            self.receiver,
            message=message,
            clear_history=clear_history,
        )

# add by ymc
def function_call_direct_reply(
    self,
    messages: Optional[List[Dict]] = None,
    sender: Optional[autogen.Agent] = None,
    config: Optional[Any] = None,
) -> Tuple[bool, Union[Dict, None]]:
    """
    Generate a reply using function call.

    "function_call" replaced by "tool_calls" as of [OpenAI API v1.1.0](https://github.com/openai/openai-python/releases/tag/v1.1.0)
    See https://platform.openai.com/docs/api-reference/chat/create#chat-create-functions
    """
    if config is None:
        config = self
    if messages is None:
        messages = self._oai_messages[sender]
    message = messages[-1]
    if ("function_call" in message and message["function_call"]) or ("tool_calls" in message and message["tool_calls"]):    
        # 返回空，阻断reply;   
        return True, None
    return False, None


class ExtendedConversableAgent(autogen.ConversableAgent):
    def __init__(self, message_processor=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.message_processor = message_processor
        # add by ymc
        self.register_reply(autogen.Agent, function_call_direct_reply)

    def receive(
        self,
        message: Union[Dict, str],
        sender: autogen.Agent,
        request_reply: Optional[bool] = None,
        silent: Optional[bool] = False,
    ):
        if self.message_processor:
            self.message_processor(sender, self, message, request_reply, silent, sender_type="agent")
        super().receive(message, sender, request_reply, silent)


""


class ExtendedGroupChatManager(autogen.GroupChatManager):
    def __init__(self, message_processor=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.message_processor = message_processor

    def receive(
        self,
        message: Union[Dict, str],
        sender: autogen.Agent,
        request_reply: Optional[bool] = None,
        silent: Optional[bool] = False,
    ):
        if self.message_processor:
            self.message_processor(sender, self, message, request_reply, silent, sender_type="groupchat")
        super().receive(message, sender, request_reply, silent)

# add by ymc
class ExtendedProxyAgent(LLMAgent):
    def __init__(self, delegate_agent: autogen.ConversableAgent, message_processor=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.delegate_agent = delegate_agent
        self.message_processor = message_processor
        

    def register_reply(
        self,
        trigger: Union[Type[Agent], str, Agent, Callable[[Agent], bool], List],
        reply_func: Callable,
        position: int = 0,
        config: Optional[Any] = None,
        reset_config: Optional[Callable] = None,
        *,
        ignore_async_in_sync_chat: bool = False,
        remove_other_reply_funcs: bool = False,
    ):
        return self.delegate_agent.register_reply(trigger, reply_func, position, config, reset_config,ignore_async_in_sync_chat, remove_other_reply_funcs)
    
    def replace_reply_func(self, old_reply_func: Callable, new_reply_func: Callable):
        return self.delegate_agent.replace_reply_func(old_reply_func, new_reply_func)

    def register_nested_chats(
        self,
        chat_queue: List[Dict[str, Any]],
        trigger: Union[Type[Agent], str, Agent, Callable[[Agent], bool], List],
        reply_func_from_nested_chats: Union[str, Callable] = "summary_from_nested_chats",
        position: int = 2,
        **kwargs,
    ) -> None:
        return self.delegate_agent.register_nested_chats(chat_queue, trigger, reply_func_from_nested_chats, position, **kwargs)

    def send(
        self,
        message: Union[Dict, str],
        recipient: Agent,
        request_reply: Optional[bool] = None,
        silent: Optional[bool] = False,
    ):
        return self.delegate_agent.send(message, recipient, request_reply, silent)    

    async def a_send(
        self,
        message: Union[Dict, str],
        recipient: Agent,
        request_reply: Optional[bool] = None,
        silent: Optional[bool] = False,
    ):
        return await self.delegate_agent.a_send(message, recipient, request_reply, silent)

    def receive(
        self,
        message: Union[Dict, str],
        sender: autogen.Agent,
        request_reply: Optional[bool] = None,
        silent: Optional[bool] = False,
    ):
        if self.message_processor:
            self.message_processor(sender, self, message, request_reply, silent, sender_type="agent")
        return self.delegate_agent.receive(message, sender, request_reply, silent)

    async def a_receive(
        self,
        message: Union[Dict, str],
        sender: Agent,
        request_reply: Optional[bool] = None,
        silent: Optional[bool] = False,
    ):
        return await self.delegate_agent.a_receive(message, sender, request_reply, silent)

    def initiate_chat(
        self,
        recipient: "ConversableAgent",
        clear_history: bool = True,
        silent: Optional[bool] = False,
        cache: Optional[AbstractCache] = None,
        max_turns: Optional[int] = None,
        summary_method: Optional[Union[str, Callable]] = "last_msg",
        summary_args: Optional[dict] = {},
        message: Optional[Union[Dict, str, Callable]] = None,
        **kwargs,
    ) -> ChatResult:
        return self.delegate_agent.initiate_chat(recipient, clear_history, silent, cache, max_turns, summary_method, summary_args, message, **kwargs)

    async def a_initiate_chat(
        self,
        recipient: "ConversableAgent",
        clear_history: bool = True,
        silent: Optional[bool] = False,
        cache: Optional[AbstractCache] = None,
        max_turns: Optional[int] = None,
        summary_method: Optional[Union[str, Callable]] = "last_msg",
        summary_args: Optional[dict] = {},
        message: Optional[Union[str, Callable]] = None,
        **kwargs,
    ) -> ChatResult:
        return await self.delegate_agent.a_initiate_chat(recipient, clear_history, silent, cache, max_turns, summary_method, summary_args, message, **kwargs)
    
    @property
    def name(self) -> str:
        return self.delegate_agent.name

    @property
    def description(self) -> str:
        return self.delegate_agent.description

    def generate_reply(
        self,
        messages: Optional[List[Dict[str, Any]]] = None,
        sender: Optional["Agent"] = None,
        **kwargs: Any,
    ) -> Union[str, Dict[str, Any], None]:
        return self.delegate_agent.generate_reply(messages, sender, **kwargs)

    async def a_generate_reply(
        self,
        messages: Optional[List[Dict[str, Any]]] = None,
        sender: Optional["Agent"] = None,
        **kwargs: Any,
    ) -> Union[str, Dict[str, Any], None]:
        return await self.delegate_agent.a_generate_reply(messages, sender, **kwargs)

    @property
    def system_message(self) -> str:
        return self.delegate_agent.system_message

    def update_system_message(self, system_message: str) -> None:
        return self.delegate_agent.update_system_message(system_message)
    
    def _raise_exception_on_async_reply_functions(self) -> None:
        return self.delegate_agent._raise_exception_on_async_reply_functions()
    
    def _prepare_chat(
        self,
        recipient: "ConversableAgent",
        clear_history: bool,
        prepare_recipient: bool = True,
        reply_at_receive: bool = True,
    ) -> None:
        return self.delegate_agent._prepare_chat(recipient, clear_history, prepare_recipient, reply_at_receive)
    
    @property
    def previous_cache(self):
        return self.delegate_agent.previous_cache
    
    @previous_cache.setter
    def previous_cache(self, value):
        self.delegate_agent.previous_cache = value
    
    @property
    def client_cache(self):
        return self.delegate_agent.client_cache
    
    @client_cache.setter
    def client_cache(self, value):
        self.delegate_agent.client_cache = value

    @property
    def last_message(self):
        return self.delegate_agent.last_message
    
    @last_message.setter
    def last_message(self, value):
        self.delegate_agent.last_message = value