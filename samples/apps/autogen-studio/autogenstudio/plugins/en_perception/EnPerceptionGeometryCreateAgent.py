import copy
from dataclasses import asdict, dataclass
import json
from os import path
import os
import sys
from typing import Any, Dict, List, Literal, Optional, Tuple, Union
from typing_extensions import Annotated
from autogen.agentchat.agent import Agent
import autogen

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from utils.function_call import *
from utils.user_message import resolve_user_image_date_uri


# 把当前路径添加到pythonpath中
sys.path.append(path.dirname(path.abspath(__file__)))
import prompt

@dataclass
class SheEditorIVector3(object):
    x: float
    y: float
    z: float

    def dict(self):
        result = asdict(self)
        return result

@dataclass
class SheEditorTransformComponent(object):
    position: Annotated[Optional[SheEditorIVector3], "位置信息（默认为坐标为 (0, 0, 0)）"]
    rotation: Annotated[Optional[SheEditorIVector3], "旋转角度信息(默认为3个方向的旋转角度都为 0， 如果 rotation.x 设置为 90， 表示物体沿着 x 轴旋转 90 度)"]
    scale: Annotated[Optional[SheEditorIVector3], "缩放信息(1表示不缩放， 默认为 1)"]

    def dict(self):
        result = asdict(self)
        return result

@dataclass
class SheEditorStandardMaterialComponent(object):
    color: Annotated[Optional[str], "外观颜色: #RGB值"]
    alpha: Annotated[Optional[float], "透明度数值。范围 0 -1。默认值为1，透明度为0时物体不可见。"]
    disableLighting: Annotated[Optional[bool], "是否禁用光照"]

    def dict(self):
        result = asdict(self)
        return result

@dataclass
class SheEditorGeoCubeComponent(object):
    edgeWidth: Annotated[Optional[float], "棱线宽度"]
    width: Annotated[Optional[float], "立方体的宽度"]
    depth: Annotated[Optional[float], "立方体的深度"]
    height: Annotated[Optional[float], "立方体的高度"]

    def dict(self):
        result = asdict(self)
        return result    

@dataclass
class SheEditorGeoCylinderComponent(object):
    edgeWidth: Annotated[Optional[float], "棱线宽度"]
    diameter: Annotated[Optional[float], "圆柱体的直径"]
    height: Annotated[Optional[float], "圆柱体的高度"]

    def dict(self):
        result = asdict(self)
        return result    

@dataclass
class SheEditorGeoConeComponent(object):
    edgeWidth: Annotated[Optional[float], "棱线宽度"]
    diameter: Annotated[Optional[float], "圆锥体的底面直径"]
    height: Annotated[Optional[float], "圆锥体的高度"]

    def dict(self):
        result = asdict(self)
        return result    

SheEditorObjectSymbol = Literal["geoCube", "geoCylinder", "geoCone"]
SheEditorComponentTypeSymbol = Literal["transform", "standardMaterial", "geoCube", "geoCylinder", "geoCone"]

def createObject(
    objectType: Annotated[SheEditorObjectSymbol, "3d几何体类型: 1.geoCube 立方体 2.geoCylinder 圆柱体 3.geoCone 圆锥体"],  
    options: Annotated[
                Union[
                    Annotated[SheEditorTransformComponent, "transform组件类型,3d几何体的位置/旋转/缩放属性"],
                    Annotated[SheEditorStandardMaterialComponent, "standardMaterial组件类型,3d几何的材质属性"],
                    Annotated[SheEditorGeoCubeComponent, "geoCube立方体组件类型"],
                    Annotated[SheEditorGeoCylinderComponent, "geoCylinder圆柱体组件类型"],
                    Annotated[SheEditorGeoConeComponent, "geoCone圆锥体组件类型"],
                    ], 
                "3d几何体组件的属性"],    
) -> str:
    return "mock:id"

def updateComponent(
    id: Annotated[str, "几何体id"],    
    componentType: Annotated[SheEditorComponentTypeSymbol, "3d几何体组件类型"],    
    properties: Annotated[
                            Union[
                                Annotated[SheEditorTransformComponent, "transform组件类型,3d几何体的位置/旋转/缩放属性"],
                                Annotated[SheEditorStandardMaterialComponent, "standardMaterial组件类型,3d几何的材质属性"],
                                Annotated[SheEditorGeoCubeComponent, "geoCube立方体组件类型"],
                                Annotated[SheEditorGeoCylinderComponent, "geoCylinder圆柱体组件类型"],
                                Annotated[SheEditorGeoConeComponent, "geoCone圆锥体组件类型"],
                                ], 
                            "3d几何体组件的属性"],    
) -> str:
    return "mock:id"

class EnPerceptionGeometryCreateAgent(autogen.ConversableAgent):
    def __init__(self, message_processor=None, context=None, llm_config=None, system_message=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.message_processor = message_processor
        self.context = context
        self.register_reply(Agent, EnPerceptionGeometryCreateAgent._en_generate_reply, position=2)
        self.register_reply(autogen.Agent, function_call_direct_reply)

        self.contains_multi_model = any(item["model"] == "internVL2" for item in llm_config["config_list"])
        if self.contains_multi_model:
            self.multi_model_agent = autogen.AssistantAgent(name="en_perception_geometry_create_assistant_multi_model", llm_config=llm_config)
        else:
            self.image_agent = autogen.AssistantAgent(name="en_perception_geometry_create_assistant_image", llm_config=llm_config, system_message=prompt.image_math_prompt)
            self.geometry_agent = autogen.AssistantAgent(name="en_perception_geometry_create_assistant_geometry", llm_config=llm_config, system_message=prompt.geometry_prompt)            
            self.geometry_agent.register_for_llm(name="createObject", description="创建3d几何体")(createObject)
            self.geometry_agent.register_for_llm(name="updateComponent", description="更新3d几何体属性。规则：1.当遇到颜色属性时，需要转换成#RGB格式")(updateComponent)


    def _en_generate_reply(
        self,
        messages: Optional[List[Dict]] = None,
        sender: Optional[Agent] = None,
        config: Optional[Any] = None,
    ) -> Tuple[bool, Union[str, Dict, None]]:     
        # content 格式  
        # {
		# 	"type": "image_url", "image_url": {"url": "https://xxx", "filekey": "xxx", "sprite": [xx,xx,xx,xx], "context_key": ""}
		# } 
        message = messages[-1]            
        image_data_uri = resolve_user_image_date_uri(message, self.context)
        
        if self.contains_multi_model:
            multi_model_agent_result = self.initiate_chat(self.multi_model_agent, message={"role": "user", "content": [{"type": "image_url", "image_url": {"url": image_data_uri}}]}, max_turns=1, silent=True)
            result = json.loads(multi_model_agent_result.summary)
            return True, result
        else:
            image_agent_result = self.initiate_chat(self.image_agent, message={"role": "user", "content": [{"type": "image_url", "image_url": {"url": image_data_uri}}]}, max_turns=1, silent=True)
            geometry_agent_result = self.initiate_chat(self.geometry_agent, message={"role": "user", "content": image_agent_result.summary}, max_turns=1, silent=True)
            return True, geometry_agent_result.chat_history[-1]


    def receive(
        self,
        message: Union[Dict, str],
        sender: autogen.Agent,
        request_reply: Optional[bool] = None,
        silent: Optional[bool] = False,
    ):
        if self.message_processor and not silent:
            self.message_processor(sender, self, message, request_reply, silent, sender_type="agent")
        super().receive(message, sender, request_reply, silent)