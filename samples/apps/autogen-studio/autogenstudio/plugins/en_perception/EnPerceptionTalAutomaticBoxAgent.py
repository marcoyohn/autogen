import json
import logging
import os
import sys
import time
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
import autogen
from autogen.agentchat.agent import Agent
from autogen.cache.cache import Cache
from autogen.oai.openai_utils import get_key
from autogenstudio.utils.user_message import *

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from utils.tal.send_sign_http import send_request


class EnPerceptionTalAutomaticBoxAgent(autogen.AssistantAgent):
    def __init__(self, message_processor=None, context=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.message_processor = message_processor        
        self.context = context
        self.register_reply(Agent, EnPerceptionTalAutomaticBoxAgent._en_generate_reply)

    def _en_generate_reply(
        self,
        messages: Optional[List[Dict]] = None,
        sender: Optional[Agent] = None,
        config: Optional[Any] = None,
    ) -> Tuple[bool, Union[str, Dict, None]]:
        message = messages[-1]
        oss_key, crop = ensure_get_user_image_oss_key_and_crop(message)
        img_base64 = resolve_user_image_base64(oss_key, self.context, crop=crop) 
        
        # 获取当前时间（东8区）
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())
        body_params = {
                "image_base64":f"{img_base64}",  
                "anchor":[0,0],
                "type": 1
            }        
        with Cache.disk("tal_automatic_box", ".cache") as cache_client:
            key = get_key(body_params)

            response: str = cache_client.get(key, None)
            if response:
                return True, {"busi_type": "agent_message_automatic_box", "role": "assistant","content": response}

            result = send_request(os.environ["TAL_ACCESS_KEY_ID"], os.environ["TAL_ACCESS_KEY_SECRET"], timestamp, os.environ["HTTP_API_URL_AUTOMATIC_BOX"], {}, body_params, "POST", "application/json")
            result = json.loads(result)
            if result["code"] == 5000001 or result["code"] == 4011005  or result["code"] == 4011007:
                # https://openai.100tal.com/documents/article/page?fromWhichSys=console&id=73
                # retry
                logging.error(
                            f"request {os.environ['HTTP_API_URL_AUTOMATIC_BOX']} error, code: {result['code']}. will retry..."
                        )
                time.sleep(3)
                timestamp = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())
                result = send_request(os.environ["TAL_ACCESS_KEY_ID"], os.environ["TAL_ACCESS_KEY_SECRET"], timestamp, os.environ["HTTP_API_URL_AUTOMATIC_BOX"], {}, body_params, "POST", "application/json")
                result = json.loads(result)

            if result["code"] != 20000:
                raise RuntimeError('图片题目分割失败')        
            automatic_box_items = [{"item_index": index+1, "item_position": item["item_position"], "item_position_show": item["item_position_show"]} for index, item in enumerate(result["data"]["data"])]
            response = json.dumps({
                "msg_type": "agent_message_automatic_box",
                "automatic_box_items": automatic_box_items
            })
            cache_client.set(key, response)
            return True, {"busi_type": "agent_message_automatic_box", "role": "assistant","content": response}

    
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
