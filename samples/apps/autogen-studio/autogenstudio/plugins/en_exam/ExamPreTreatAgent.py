import copy
from io import BytesIO
import json
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import requests
import autogen
from autogen.agentchat.agent import Agent
from PIL import Image

import sys
from os import path

from autogen.agentchat.contrib.img_utils import get_image_data, get_pil_image
# 把当前路径添加到pythonpath中
sys.path.append(path.dirname(path.abspath(__file__)))
from ExamAutomaticBoxAgent import ExamAutomaticBoxAgent
from ExamSolveAgent import ExamSolveAgent
from ExamMathExprAgent import ExamMathExprAgent

class ExamPreTreatAgent(autogen.ConversableAgent):
    def __init__(self, message_processor=None, llm_config=None, *args, **kwargs):
        super().__init__(llm_config=llm_config, *args, **kwargs)
        self.message_processor = message_processor    
        self.register_reply(Agent, ExamPreTreatAgent._generate_exam_pre_treat_reply)
        # init nested agent    
        self.automatic_box_agent = ExamAutomaticBoxAgent(name="en_exam_automatic_box_assistant", message_processor=message_processor)
        llm_config = copy.deepcopy(llm_config)
        llm_config["config_list"] = [
            item
            for item in llm_config["config_list"]
            if item["model"] == "OPENAI_GPT_4_O_PREVIEW"
        ]
        self.solve_agent = ExamSolveAgent(name="en_exam_solve_assistant", message_processor=message_processor, llm_config=llm_config)
        self.math_expr_agent = ExamMathExprAgent(name="en_exam_math_expr_assistant", message_processor=message_processor, llm_config=llm_config)
        

    def _generate_exam_pre_treat_reply(
        self,
        messages: Optional[List[Dict]] = None,
        sender: Optional[Agent] = None,
        config: Optional[Any] = None,
    ) -> Tuple[bool, Union[str, Dict, None]]:        
        # call automatic box agent
        # TODO 测试写死message 消息 https://cos-public.seewo.com/public_appId-dev/ymc_jiheti_1.png
        # message = messages[-1]
        message = {
                        "role": "user",
                        "content": [                            
                            {
                                "type": "image_url", "image_url": {"url": "https://cos-public.seewo.com/public_appId-dev/ymc_jiheti_1.png"}
                            }
                        ]
                    }
        automatic_box_agent_result = self.initiate_chat(self.automatic_box_agent, message=message, max_turns=1)
        # parse automatic box to image
        image = get_pil_image(message["content"][0]["image_url"]["url"])
        automatic_box_result = json.loads(automatic_box_agent_result.summary)
        for box_item in automatic_box_result["automatic_box_items"]:
            positions = box_item["item_position_show"]
            # 根据给定的坐标裁剪图片
            cropped_image = image.crop((positions[0][0], positions[0][1], positions[2][0], positions[2][1]))        
            cropped_image_base64 = get_image_data(cropped_image, use_b64=True)
            
            # image mssage
            message = {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "这是几何题图片："},
                            {
                                "type": "image_url", "image_url": {"url": f"data:image/png;base64,{cropped_image_base64}"}
                            }
                        ]
                    }
            # call exam solve agent            
            solve_agent_result = self.initiate_chat(self.solve_agent, message=message, max_turns=1)
            box_item["solve"] = solve_agent_result.summary
            # call exam math expr agent
            math_expr_agent_result = self.initiate_chat(self.math_expr_agent, message=message, max_turns=1)
            box_item["math_expr"] = math_expr_agent_result.summary

        # return sumary message
        return True, json.dumps(automatic_box_result, ensure_ascii=False)