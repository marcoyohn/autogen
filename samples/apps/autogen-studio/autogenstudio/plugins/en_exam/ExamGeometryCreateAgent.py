from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Literal, Optional, Tuple, Union
from typing_extensions import Annotated
import autogen

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
    objectType: Annotated[SheEditorObjectSymbol, "3d几何体类型"],  
    options: Annotated[
                Union[
                    Annotated[SheEditorTransformComponent, "transform组件类型,3d几何体的位置/旋转/缩放属性"],
                    Annotated[SheEditorStandardMaterialComponent, "standardMaterial组件类型,3d几何的材质属性"],
                    Annotated[SheEditorGeoCubeComponent, "geoCube立方体组件类型"],
                    Annotated[SheEditorGeoCylinderComponent, "geoCone圆柱体组件类型"],
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
                                Annotated[SheEditorGeoCylinderComponent, "geoCone圆柱体组件类型"],
                                Annotated[SheEditorGeoConeComponent, "geoCone圆锥体组件类型"],
                                ], 
                            "3d几何体组件的属性"],    
) -> str:
    return "mock:id"

class ExamGeometryCreateAgent(autogen.ConversableAgent):
    def __init__(self, message_processor=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.message_processor = message_processor
        self.register_reply(autogen.Agent, function_call_direct_reply)
        if self.llm_config:
            self.register_for_llm(name="createObject", description="创建3d几何体")(createObject)
            self.register_for_llm(name="updateComponent", description="更新3d几何体属性。规则：1.当遇到颜色属性时，需要转换成#RGB格式")(updateComponent)


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