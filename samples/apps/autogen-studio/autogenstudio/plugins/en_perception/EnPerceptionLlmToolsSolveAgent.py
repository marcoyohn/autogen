import copy
import json
import logging
import os
import sys
import time
from typing import Any, Callable, Dict, List, Literal, Optional, Tuple, Union
import autogen
from autogen.agentchat.agent import Agent
from autogen.agentchat.conversable_agent import ConversableAgent
from autogen._pydantic import model_dump
from autogenstudio.utils.user_message import *



ExamSolveTypeSymbol = Literal["solve", "math_expr"]

class EnPerceptionLlmToolsSolveAgent(autogen.AssistantAgent):
    def __init__(self, message_processor=None, context=None, item_index: int = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.message_processor = message_processor     
        self.context = context   
        self.item_index = item_index
        # Override the `generate_oai_reply`
        self.replace_reply_func(ConversableAgent.generate_oai_reply, EnPerceptionLlmToolsSolveAgent.generate_oai_reply)
        self.replace_reply_func(
            ConversableAgent.a_generate_oai_reply,
            EnPerceptionLlmToolsSolveAgent.a_generate_oai_reply,
        )

    def generate_oai_reply(
        self,
        messages: Optional[List[Dict]] = None,
        sender: Optional[Agent] = None,
        config: Optional[Any] = None,
    ) -> Tuple[bool, Union[str, Dict, None]]:
        
        """Generate a reply using autogen.oai."""
        client = self.client if config is None else config
        if client is None:
            return False, None
        if messages is None:
            messages = self._oai_messages[sender]
        
        new_messages = []
        for message in messages:
            if isinstance(message, dict) and "content" in message and isinstance(message["content"], list):
                message = copy.deepcopy(message)
                for item in message["content"]:
                    if isinstance(item, dict) and "image_url" in item:
                        oss_key, crop = ensure_get_user_image_oss_key_and_crop(message)
                        image_btyes = resolve_user_image_bytes(oss_key, self.context)                        
                        item["image_url"]["url"] = pil_to_data_uri(Image.open(BytesIO(image_btyes)).crop(tuple(crop)))                        

            new_messages.append(message)
        

        messages_with_b64_img = self._oai_system_message + new_messages

        response = None
        context = messages[-1].pop("context", None)
        try:
            # TODO: #1143 handle token limit exceeded error            
            response = client.create(context=context, messages=messages_with_b64_img, agent=self)
        except Exception as e:
            # retry
            logging.error(f"request oai error: {e}. will retry...")
            time.sleep(3)
            response = client.create(context=context, messages=messages_with_b64_img)

        # TODO: line 301, line 271 is converting messages to dict. Can be removed after ChatCompletionMessage_to_dict is merged.
        extracted_response = client.extract_text_or_completion_object(response)[0]
        if not isinstance(extracted_response, str):
            extracted_response = model_dump(extracted_response)
        elif extracted_response == "null":
            extracted_response = ""
        try:
            tools = json.loads(extracted_response)
            if not isinstance(tools, List):
                tools = []
                logging.error(f"tools response not array: {extracted_response}")
        except Exception as e:
            tools = []
            logging.error(f"tools response not json: {extracted_response}")

        return True, {"busi_type": "agent_message_tool_resolve_patch", "role": "assistant","content": json.dumps({"msg_type": "agent_message_tool_resolve_patch", "automatic_box_items": [{"item_index": self.item_index, "tools": tools}]}, ensure_ascii=False)}
    

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
