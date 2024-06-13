import json
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
import autogen
from autogen.agentchat.agent import Agent

_prompt = '''

# 角色：立体几何题图片识别专家

## 技能：
识别几何体图片，翻译为数学公式表达

## 目标
1. 翻译为数学公式表达(该表达能够还原出几何体)

## 要求
- 请输出你的思考过程，以辅助我的prompt优化
- 当无法使用数学公式表达时，不要硬套，可以使用伪代码代替数学公式表达
- 数学公式表达/伪代码中出现变量时，需要进一步估算并假设变量为具体的数值，把数值代入公式得到实例化的公式
- 不同几何图采用不同的数学表达方式，见子章节

### 数学公式表达：三角形
- 使用点坐标表达
- 图片中有有标示角度的，额外针对标示的角使用角度表达，其它角不需要表达

### 数学公式表达：圆
- 使用圆心坐标 + 半径表达

### 数学公式表达：通用
- 使用点坐标、线、面表达
- 图片中有有标示角度的，额外针对标示的角使用角度表达，其它角不需要表达


## 工作流程
1. 从几何题的知识角度，先理解几何体的组成和形状
2. 把理解翻译成数学公式表达（通过数学公式表达能够还原出几何体）


'''

class ExamMathExprAgent(autogen.AssistantAgent):
    def __init__(self, message_processor=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        super().update_system_message(_prompt)
        self.message_processor = message_processor       

    
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