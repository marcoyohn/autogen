import concurrent.futures
import json
from os import path
import os
import sys
from typing import Any, Dict, List, Literal, Optional, Tuple, Union
from autogen.agentchat.agent import Agent
import autogen
from autogen.agentchat.conversable_agent import ConversableAgent
from autogenstudio.utils.user_message import *
from autogenstudio.web.app import thread_pool_agent


# 把当前路径添加到pythonpath中
sys.path.append(path.dirname(path.abspath(__file__)))
import prompt
from EnPerceptionTalAutomaticBoxAgent import EnPerceptionTalAutomaticBoxAgent
from EnPerceptionCvteAutomaticBoxAgent import EnPerceptionCvteAutomaticBoxAgent
from EnPerceptionLlmToolsSolveAgent import EnPerceptionLlmToolsSolveAgent
from utils.function_call import *


class EnPerceptionRecognitionAgent(autogen.ConversableAgent):

    def __init__(self, message_processor=None, context=None, llm_config=None, *args, **kwargs):
        super().__init__(llm_config=llm_config, *args, **kwargs)
        self.message_processor = message_processor
        self.context = context or {}
        self.register_reply(Agent, EnPerceptionRecognitionAgent._en_generate_reply, position=2)
        self.register_reply(autogen.Agent, function_call_direct_reply)
        box_provider = os.environ.get("BOX_PROVIDER") or "tal"
        if box_provider == "tal":
            self.box_agent = EnPerceptionTalAutomaticBoxAgent(name="en_perception_recognition_assistant_box", message_processor=message_processor, context=self.context)
        elif box_provider == "cvte":
            self.box_agent = EnPerceptionCvteAutomaticBoxAgent(name="en_perception_recognition_assistant_box", message_processor=message_processor, context=self.context)
        else:
            raise RuntimeError('BOX_PROVIDER配置错误，只能是tal或cvte')

    def _en_generate_reply(
        self,
        messages: Optional[List[Dict]] = None,
        sender: Optional[Agent] = None,
        config: Optional[Any] = None,
    ) -> Tuple[bool, Union[str, Dict, None]]:     
        message = messages[-1]   
        oss_key, crop = ensure_get_user_image_oss_key_and_crop(message)
        image_url = {"url": f"oss:{oss_key}"}
        if crop is not None:
            image_url["crop"] = crop
        box_result = self.initiate_chat(self.box_agent, message={"role": "user", "content": [{"type": "image_url", "image_url": image_url}]}, max_turns=1, silent=False)
        box = json.loads(box_result.summary)     
        futures = []   
        for box_item in box["automatic_box_items"]:
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
            tools_solve_agent = EnPerceptionLlmToolsSolveAgent(name="en_perception_recognition_assistant_tools_solve", message_processor=self.message_processor, context=self.context, llm_config=self.llm_config, system_message=prompt.tools_solve_prompt, item_index=box_item["item_index"])
            futures.append(thread_pool_agent.submit(lambda agent, message, box_item: self.run_llm_tools_solve(agent, message, box_item), tools_solve_agent, message, box_item))       

        # 获取已完成的任务结果
        for future in concurrent.futures.as_completed(futures):
            future.result()

        return True, {"role": "assistant","content": "TERMINATE"}

    def run_llm_tools_solve(self, agent: ConversableAgent, message: Dict, box_item: Dict):
        self.initiate_chat(agent, message=message, max_turns=1)
        # 不需要汇集所有的结果
        # tools_solve_result = self.initiate_chat(agent, message=message, max_turns=1)
        # tools_solve = json.loads(tools_solve_result.summary)

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