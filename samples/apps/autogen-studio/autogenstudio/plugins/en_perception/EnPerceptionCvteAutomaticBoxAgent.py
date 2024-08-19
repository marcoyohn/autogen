from hashlib import sha1
import json
import logging
import os
import sys
import time
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
import uuid

import requests
import autogen
from autogen.agentchat.agent import Agent
from autogen.cache.cache import Cache
from autogen.oai.openai_utils import get_key
from autogenstudio.utils.user_message import *

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from utils.tal.send_sign_http import send_request

class EnPerceptionCvteAutomaticBoxAgent(autogen.AssistantAgent):
    def __init__(self, message_processor=None, context=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.message_processor = message_processor        
        self.context = context
        self.register_reply(Agent, EnPerceptionCvteAutomaticBoxAgent._en_generate_reply)
        self.url = os.environ["HTTP_API_URL_CVTE_AUTOMATIC_BOX"]
        self.app_id = os.environ["CVTE_BOX_ACCESS_APP_ID"]
        self.api_key = os.environ["CVTE_BOX_ACCESS_KEY_ID"]
        self.secret_key = os.environ["CVTE_BOX_ACCESS_KEY_SECRET"]


    def _en_generate_reply(
        self,
        messages: Optional[List[Dict]] = None,
        sender: Optional[Agent] = None,
        config: Optional[Any] = None,
    ) -> Tuple[bool, Union[str, Dict, None]]:
        message = messages[-1]
        oss_key, crop = ensure_get_user_image_oss_key_and_crop(message)
        img_base64 = resolve_user_image_base64(oss_key, self.context, crop=crop)        
                
        task_id = str(uuid.uuid4())
        body_params = {
            "im_base64": img_base64, 
            "task_id": task_id
        }        
        with Cache.disk("cvte_automatic_box", ".cache") as cache_client:
            key = get_key({"im_base64": img_base64})

            response: str = cache_client.get(key, None)
            if response:
                return True, {"busi_type": "agent_message_automatic_box", "role": "assistant","content": response}
            t = int(time.time())
            need_sign_str = "t={0}&aid={1}&akey={2}&skey={3}".format(t, self.app_id, self.api_key, self.secret_key)
            sign = sha1(need_sign_str.encode("utf8")).hexdigest()
            headers = {
                "X-C-AppId": self.app_id,
                "X-C-ApiKey": self.api_key,
                "X-C-Signature": sign,
                "X-C-AuthMode": "signature",
                "X-C-Timestamp": str(t)
            }
            data = json.dumps(body_params)
            result = requests.post(self.url, data=data, headers=headers)
            result = json.loads(result.text)
            if result["statusCode"] == -300:
                # TODO 需要重试的状态码
                # retry
                logging.error(
                            f"request {self.url} error, code: {result['code']}. will retry..."
                        )
                time.sleep(3)
                t = int(time.time())
                need_sign_str = "t={0}&aid={1}&akey={2}&skey={3}".format(t, self.app_id, self.api_key, self.secret_key)
                sign = sha1(need_sign_str.encode("utf8")).hexdigest()
                headers = {
                    "X-C-AppId": self.app_id,
                    "X-C-ApiKey": self.api_key,
                    "X-C-Signature": sign,
                    "X-C-AuthMode": "signature",
                    "X-C-Timestamp": str(t)
                }
                task_id = str(uuid.uuid4())
                body_params = {
                    "im_base64": img_base64, 
                    "task_id": task_id
                }     
                data = json.dumps(body_params)
                result = requests.post(self.url, data=data, headers=headers)
                result = json.loads(result.text)

            if result["statusCode"] != 0:
                raise RuntimeError('图片题目分割失败')    
            automatic_box_items = []
            for index, item in enumerate(result["data"]["result"]):
                left_top, bottom_down =  item["exercise_body_box"].split(';')[:2]
                left_top = left_top.split(',')
                left_top_x = int(left_top[0])
                left_top_y = int(left_top[1])
                bottom_down = bottom_down.split(',')    
                bottom_down_x = int(bottom_down[0])
                bottom_down_y = int(bottom_down[1])
                automatic_box_items.append({"item_index": index+1,"item_position_show": [[left_top_x,left_top_y],[left_top_y,bottom_down_x],[bottom_down_x,bottom_down_y],[bottom_down_y,left_top_x]]})
            
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
