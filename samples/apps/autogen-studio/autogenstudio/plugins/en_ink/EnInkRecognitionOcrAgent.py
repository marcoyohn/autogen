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

class EnInkRecognitionOcrAgent(autogen.AssistantAgent):
    def __init__(self, message_processor=None, context=None, ocr_type=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.message_processor = message_processor        
        self.context = context
        if ocr_type == "eng" or ocr_type == "chn" or ocr_type == "symbol":
            self.ocr_type = 0
        elif ocr_type == "pinyin":
            self.ocr_type = 1
        elif ocr_type == "formula":
            self.ocr_type = 2
        else:
            self.ocr_type = 0
        self.register_reply(Agent, EnInkRecognitionOcrAgent._en_generate_reply)
        self.url = os.environ["HTTP_API_URL_CVTE_INK_OCR"]
        self.app_id = os.environ["CVTE_INK_ACCESS_APP_ID"]
        self.api_key = os.environ["CVTE_INK_ACCESS_KEY_ID"]
        self.secret_key = os.environ["CVTE_INK_ACCESS_KEY_SECRET"]


    def _en_generate_reply(
        self,
        messages: Optional[List[Dict]] = None,
        sender: Optional[Agent] = None,
        config: Optional[Any] = None,
    ) -> Tuple[bool, Union[str, Dict, None]]:
        # {"block_index": 1, "items": [{"item_index": 1, "type": "", "strokes": {"id": []}}]}
        message = messages[-1]
        input_strokers = try_get_from_context(message.get("content", None), self.context)
                
        request_item_index = {}
        request_strokers = []
        for item_index, item in enumerate(input_strokers["items"]):
            request_item_index[str(item_index)] = item["item_index"]
            request_item_strokers = []
            request_strokers.append({"strokes": request_item_strokers, "rec_mode": self.ocr_type})
            for stroke_id, points in item["strokes"].items():
                points_str = ""
                points_last_index = len(points) - 1
                for i, point in enumerate(points):
                    if i == points_last_index:
                        points_str = f"{points_str}{point}"
                    elif i % 2 != 0:
                        points_str = f"{points_str}{point};"
                    else:
                        points_str = f"{points_str}{point},"                
                request_item_strokers.append({"stroke_id": stroke_id, "points": points_str})
        task_id = str(uuid.uuid4())
        body_params = {
            "user_task_id": task_id,
            "stroke_list": request_strokers
        }   
        
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
                "user_task_id": task_id,
                "stroke_list": [{"strokes": request_strokers}]
            }   
            data = json.dumps(body_params)
            result = requests.post(self.url, data=data, headers=headers)
            result = json.loads(result.text)

        if result["statusCode"] != 0:
            raise RuntimeError('手写批注ocr识别失败')    
                
        result_item = []        
        for index, item_result in enumerate(result["data"]["result"]):                        
            result_item.append({"item_index": request_item_index[str(index)], "content": item_result["content"]})

        content_json_str = json.dumps({
            "blocks": [{"block_index": input_strokers["block_index"], "items": result_item}]
        })
        
        return True, {"busi_type": "agent_message_structured_item_detail_patch", "role": "assistant","content": content_json_str}

    
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
