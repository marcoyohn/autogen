import json
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
import autogen
from autogen.agentchat.agent import Agent

_prompt = '''

# 角色：立体几何题图片识别专家

## 技能：
识别几何题图片，给出解题过程和答题

## 目标
1. 给出解题思路和详细的过程
2. 给出答案

## 要求
- 请输出你的思考过程，以辅助我的prompt优化
- 当无法使用数学公式表达时，不要硬套，可以使用伪代码代替数学公式表达
- 数学公式表达/伪代码中出现变量时，需要进一步估算并假设变量为具体的数值，把数值代入公式得到实例化的公式
- 不同几何图采用不同的数学表达方式，见子章节

'''

class ExamSolveAgent(autogen.AssistantAgent):
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
