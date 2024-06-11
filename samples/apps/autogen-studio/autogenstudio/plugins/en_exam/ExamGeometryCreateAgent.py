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
    x: Annotated[float, "x坐标"]
    y: Annotated[float, "y坐标"]
    z: Annotated[float, "z坐标"]

    def dict(self):
        result = asdict(self)
        return result
    
@dataclass
class SheEditorPoint(object):
    coordinates: Annotated[List[float], "坐标"]
    name: Annotated[str, "名称"]
    

    def dict(self):
        result = asdict(self)
        return result

@dataclass
class Polygon(object):
    name: Annotated[str, "名称"]
    points: Annotated[List[Annotated[SheEditorPoint,"顶点"]], "顶点集合"]
    

    def dict(self):
        result = asdict(self)
        return result

#@user_proxy.register_for_execution("create_box")    
#@math_bot.register_for_llm(description="创建立方体，返回各顶点坐标")
# def create_box(
#     height: Annotated[float, "设置高度Y"],
#     width: Annotated[float, "设置长度X"],
#     depth: Annotated[float, "设置宽度Z，也称为深度"],
# ) -> List[Dict]:
#     return [SheEditorIVector3(x=0,y=0,z=0).dict(), SheEditorIVector3(x=0,y=1,z=0).dict(), SheEditorIVector3(x=1,y=1,z=0).dict(), SheEditorIVector3(x=1,y=0,z=0).dict(), SheEditorIVector3(x=0,y=0,z=1).dict(), SheEditorIVector3(x=0,y=1,z=1).dict(), SheEditorIVector3(x=1,y=1,z=1).dict(), SheEditorIVector3(x=1,y=0,z=1).dict()]

# @user_proxy.register_for_execution("create_line")  
# @math_bot.register_for_llm(description="创建线段")
# def create_line(
#     start_point: Annotated[SheEditorIVector3, "起始点"],
#     end_point: Annotated[SheEditorIVector3, "结束点"],
#     start_point_label: Annotated[str, "起始点的名称"],
#     end_point_label: Annotated[str, "结束点的名称"],
# ) -> bool:
#     return True


def create_polygons(
    polygons: Annotated[List[Annotated[Polygon, "多边形"]], "多边形集合"],    
) -> bool:
    return True


def create_circle(
    radius: Annotated[float, "半径"],    
) -> bool:
    return True

# @user_proxy.register_for_execution("create_label")  
# @math_bot.register_for_llm(description="标记顶点的名称")
# def create_label(
#     point: Annotated[SheEditorIVector3, "顶点"],
#     lable_name: Annotated[str, "顶点的名称"],
# ) -> bool:
#     return True

class ExamGeometryCreateAgent(autogen.ConversableAgent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.register_reply(autogen.Agent, function_call_direct_reply)
        if self.llm_config:
            self.register_for_llm(name="create_circle", description="创建圆")(create_circle)
            self.register_for_llm(name="create_polygons", description="创建多个多边形")(create_polygons)

