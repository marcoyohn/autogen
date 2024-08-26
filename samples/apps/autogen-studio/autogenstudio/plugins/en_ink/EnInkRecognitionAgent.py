import concurrent.futures
import json
from os import path
import os
import sys
from typing import Any, Dict, List, Literal, Optional, Tuple, Union
import uuid
from autogen.agentchat.agent import Agent
import autogen
from autogenstudio.utils.user_message import *
from autogenstudio.web.app import thread_pool_agent
from autogenstudio.utils.function_call import *

# 把当前路径添加到pythonpath中
sys.path.append(path.dirname(path.abspath(__file__)))
from EnInkRecognitionStructureAgent import EnInkRecognitionStructureAgent
from EnInkRecognitionOcrAgent import EnInkRecognitionOcrAgent



class EnInkRecognitionAgent(autogen.ConversableAgent):
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=10, thread_name_prefix="ThreadPoolExecutor_EnPerceptionRecognition")

    def __init__(self, message_processor=None, context=None, llm_config=None, *args, **kwargs):
        super().__init__(llm_config=llm_config, *args, **kwargs)
        self.message_processor = message_processor
        self.context = context or {}
        self.register_reply(Agent, EnInkRecognitionAgent._en_generate_reply, position=2)
        self.register_reply(autogen.Agent, function_call_direct_reply)
        self.structure_agent = EnInkRecognitionStructureAgent(name="en_ink_recognition_assistant_structure", message_processor=message_processor, context=self.context)

    def _en_generate_reply(
        self,
        messages: Optional[List[Dict]] = None,
        sender: Optional[Agent] = None,
        config: Optional[Any] = None,
    ) -> Tuple[bool, Union[str, Dict, None]]:     
        message = messages[-1]   
        objects: List[Dict] = [item["object"] for item in message["content"] if item["type"] == "object"]
        if objects == 0:
            raise RuntimeError('输入格式不正确, 正确格式: "content": [{"type":"object": "object": {"strokes":{"id_xx2":[431, 2531, 2531, 2456], "id_xx2":[]}]}}] ')
        
        input_strokers = objects[0]["strokes"]
        self.context["input"] = input_strokers
        structure_result = self.initiate_chat(self.structure_agent, message={"role": "user", "content": [{"type": "context", "context": "input"}]}, max_turns=1, silent=False)
        structure = json.loads(structure_result.summary)     
        futures = []   
        for block in structure["blocks"]:
            block_index = block["block_index"]
            batch_items_type = None
            batch_size_limit = 10
            batch_size = 0
            total_index = len(block["items"]) - 1
            for i, item in enumerate(block["items"]):
                batch_size = batch_size + 1                
                if batch_items_type is None:
                    batch_items_type = item["type"]
                    batch_items = {"block_index": block_index, "items": []}

                if batch_items_type != item["type"] or batch_size > batch_size_limit:
                    #处理
                    futures.append(self._run_ocr_agent(batch_items))
                    
                    batch_items_type = None
                    batch_items = {"block_index": block_index, "items": []}
                    batch_size = 1
                
                item_strokes = {}
                for strokes_id in item["strokes_id_list"]:
                    item_strokes[strokes_id] = input_strokers[strokes_id]
                batch_items["items"].append({"item_index": item["item_index"], "type": item["type"], "strokes": item_strokes})
                if i == total_index:                        
                    futures.append(self._run_ocr_agent(batch_items))
                    
                
        for future in concurrent.futures.as_completed(futures):
            future.result()

        return True, {"role": "assistant","content": "TERMINATE"}

    def _run_ocr_agent(self, batch_items: Dict):
        context_key = str(uuid.uuid4())
        self.context[context_key] = batch_items
        message = {"role": "user", "content": [{"type": "context", "context": context_key}]}
        # call exam solve agent     
        ocr_agent = EnInkRecognitionOcrAgent(name="en_ink_recognition_assistant_ocr", message_processor=self.message_processor, context=self.context, llm_config=self.llm_config)
        return thread_pool_agent.submit(lambda agent, message: self.initiate_chat(agent, message=message, max_turns=1), ocr_agent, message)
        

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