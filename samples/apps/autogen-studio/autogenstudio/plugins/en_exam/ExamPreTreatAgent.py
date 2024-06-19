import concurrent.futures
import copy
from io import BytesIO
import json
import os
from typing import Any, Dict, List, Optional, Tuple, Union

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

import util.prompt

class ExamPreTreatAgent(autogen.ConversableAgent):
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=10, thread_name_prefix="ThreadPoolExecutor_ExamPreTreat")
    
    def __init__(self, message_processor=None, llm_config=None, *args, **kwargs):
        super().__init__(llm_config=llm_config, *args, **kwargs)
        self.message_processor = message_processor    
        self.register_reply(Agent, ExamPreTreatAgent._generate_exam_pre_treat_reply, position=2)
        # init nested agent    
        self.context = {}
        self.automatic_box_agent = ExamAutomaticBoxAgent(name="en_exam_automatic_box_assistant", message_processor=message_processor, context=self.context)
        llm_config = copy.deepcopy(llm_config)
        llm_config["config_list"] = [
            item
            for item in llm_config["config_list"]
            if item["model"] == "OPENAI_GPT_4_O_PREVIEW"
        ]
        self.exam_solve_llm_config = llm_config        
        

    def _generate_exam_pre_treat_reply(
        self,
        messages: Optional[List[Dict]] = None,
        sender: Optional[Agent] = None,
        config: Optional[Any] = None,
    ) -> Tuple[bool, Union[str, Dict, None]]:     
        # content 格式  
        # {
		# 	"type": "image_url", "image_url": {"url": "https://xxx", "filekey": "xxx", "sprite": [xx,xx,xx,xx]}
		# } 

        # call automatic box agent
        message = messages[-1]    
        if "mock_enabled" in os.environ and os.environ["mock_enabled"] == "1" and (isinstance(message["content"], str) or len([item for item in message["content"] if item["type"] == "image_url"]) == 0):
            # TODO 去掉这逻辑 测试写死message 消息 https://cos-public.seewo.com/public_appId-dev/ymc_jiheti_1.png
            message = {
                            "role": "user",
                            "content": [                            
                                {
                                    "type": "image_url", "image_url": {"url": "https://cos-public.seewo.com/public_appId-dev/ymc_jiheti_1.png"}
                                }
                            ]
                        }
        images: List[Dict] = [item for item in message["content"] if item["type"] == "image_url"]
        images_len = len(images)
        if images_len == 0:
            raise RuntimeError('请输入一张图片')
        if images_len > 1:
            raise RuntimeError('输入只支持一张图片')
        image_url_dict = images[0]["image_url"]
        image_url = image_url_dict["url"]
        filekey = image_url_dict.get("filekey", None) or image_url
        image = get_pil_image(image_url)
        self.context[f"image:{filekey}"] = image
        automatic_box_agent_result = self.initiate_chat(self.automatic_box_agent, message={"role": "user", "content": [images[0]]}, max_turns=1)
        # parse automatic box to image        
        automatic_box_result = json.loads(automatic_box_agent_result.summary)
        automatic_box_result["msg_type"] = "agent_response"
        self.context["result"] = automatic_box_result
        futures = []
        for box_item in automatic_box_result["automatic_box_items"]:
            positions = box_item["item_position_show"]
            # 根据给定的坐标裁剪图片
            cropped_image = image.crop((positions[0][0], positions[0][1], positions[2][0], positions[2][1]))        
            self.context[f"image:{filekey}:{positions[0][0]}-{positions[0][1]}-{positions[2][0]}-{positions[2][1]}"] = cropped_image 
            # image mssage
            message = {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "这是几何题图片："},
                            {
                                "type": "image_url", "image_url": {"sprite": [positions[0][0], positions[0][1], positions[2][0], positions[2][1]],"filekey": filekey, "url": image_url}
                            }
                        ]
                    }
            # call exam solve agent     
            solve_agent = ExamSolveAgent(name="en_exam_solve_assistant", message_processor=self.message_processor, context=self.context, exam_solve_type="solve", llm_config=self.exam_solve_llm_config)
            solve_agent.update_system_message(util.prompt.exam_solve_prompt)
            futures.append(ExamPreTreatAgent.executor.submit(lambda agent, msg:self.initiate_chat(agent, message=msg, max_turns=1), solve_agent, message))       
            # self.initiate_chat(self.solve_agent, message=message, max_turns=1)
            # call exam math expr agent
            math_expr_agent = ExamSolveAgent(name="en_exam_math_expr_assistant", message_processor=self.message_processor, context=self.context, exam_solve_type="math_expr", llm_config=self.exam_solve_llm_config)
            math_expr_agent.update_system_message(util.prompt.exam_math_prompt)
            futures.append(ExamPreTreatAgent.executor.submit(lambda agent, msg:self.initiate_chat(agent, message=msg, max_turns=1), math_expr_agent, message))
            # self.initiate_chat(self.math_expr_agent, message=message, max_turns=1)

        # 获取已完成的任务结果
        for future in concurrent.futures.as_completed(futures):
            future.result()
        # return sumary message
        # check result for test
        # for box_item in automatic_box_result["automatic_box_items"]:
        #     if not (box_item.get("solve", None) and box_item.get("math_expr", None)):
        #         raise RuntimeError("")

        return True, json.dumps(automatic_box_result, ensure_ascii=False)
    
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
