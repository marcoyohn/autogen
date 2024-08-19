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

from autogen.agentchat.contrib.img_utils import get_pil_image, pil_to_data_uri
from autogen.cache.cache import Cache
from autogenstudio.utils.user_message import *
# 把当前路径添加到pythonpath中
sys.path.append(path.dirname(path.abspath(__file__)))
from ExamAutomaticBoxAgent import ExamAutomaticBoxAgent
from ExamSolveAgent import ExamSolveAgent

import util.prompt

class ExamPreTreatAgent(autogen.ConversableAgent):
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=10, thread_name_prefix="ThreadPoolExecutor_ExamPreTreat")
    
    def __init__(self, message_processor=None, context=None, llm_config=None, *args, **kwargs):
        super().__init__(llm_config=llm_config, *args, **kwargs)
        self.message_processor = message_processor   
        self.context = context 
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
        oss_key, crop = ensure_get_user_image_oss_key_and_crop(message)
        image_url = {"url": f"oss:{oss_key}"}
        if crop is not None:
            image_url["crop"] = crop
        automatic_box_agent_result = self.initiate_chat(self.automatic_box_agent, message={"role": "user", "content": [{"type": "image_url", "image_url": image_url}]}, max_turns=1, silent=False)
        # parse automatic box to image        
        automatic_box_result = json.loads(automatic_box_agent_result.summary)
        automatic_box_result["msg_type"] = "agent_response"
        self.context["result"] = automatic_box_result
        futures = []
        for box_item in automatic_box_result["automatic_box_items"]:
            positions = box_item["item_position_show"]            
            # image mssage
            message = {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url", "image_url": {"crop": [positions[0][0], positions[0][1], positions[2][0], positions[2][1]], "url": f"oss:{oss_key}"}
                            }
                        ]
                    }            
            # call exam solve agent     
            solve_agent = ExamSolveAgent(name="en_exam_solve_assistant", message_processor=self.message_processor, context=self.context, exam_solve_type="solve", llm_config=self.exam_solve_llm_config, item_index=box_item["item_index"])
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
            self.message_processor(sender, self, message, request_reply, silent, sender_type="agent", context=self.context)
        super().receive(message, sender, request_reply, silent)
