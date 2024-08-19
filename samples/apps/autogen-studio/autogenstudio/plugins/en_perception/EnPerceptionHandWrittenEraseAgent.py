import base64
import hashlib
from io import BytesIO
import json
import logging
import os
import sys
import time
from typing import Any, Dict, List, Optional, Tuple, Union

import requests
import autogen
from autogen.agentchat.agent import Agent
from autogen.agentchat.contrib.img_utils import convert_base64_to_data_uri, get_image_data
from autogen.cache.cache import Cache
from autogen.oai.openai_utils import get_key
from autogen.oss.oss_utils import upload_image_data
from autogenstudio.utils.user_message import *



class EnPerceptionHandWrittenEraseAgent(autogen.AssistantAgent):
    def __init__(self, message_processor=None, context=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.message_processor = message_processor        
        self.context = context
        self.register_reply(Agent, EnPerceptionHandWrittenEraseAgent._en_generate_reply, position=2)

        self.url = os.environ['HTTP_API_URL_TI_HAND_WRITTEN_ERASE']
        self.app_id = os.environ["TI_ACCESS_KEY_ID"]
        self.secret_code = os.environ["TI_ACCESS_KEY_SECRET"]

    def _en_generate_reply(
        self,
        messages: Optional[List[Dict]] = None,
        sender: Optional[Agent] = None,
        config: Optional[Any] = None,
    ) -> Tuple[bool, Union[str, Dict, None]]:
        message = messages[-1]
        oss_key, crop = ensure_get_user_image_oss_key_and_crop(message)
        image_bytes = resolve_user_image_bytes(oss_key, self.context, crop=crop)             

        with Cache.disk("ti_hand_written_erase", ".cache") as cache_client:
            url_query = "dewarp=0&binarization=1"
            key = hashlib.md5(image_bytes).hexdigest() + str(len(image_bytes)) + str(image_bytes[-10:])
            oss_key_file: str = cache_client.get(key, None)
            if oss_key_file:
                file_key, app_id = oss_key_file.split("@")
                return True, {"busi_type": "agent_message_hand_written_erase", "role": "assistant","content": [{"type": "image_url", "image_url": { "url": f"oss:{oss_key_file}"}}]}

            head = {}
            head['x-ti-app-id'] = self.app_id
            head['x-ti-secret-code'] = self.secret_code
            result = requests.post(f'{self.url}?{url_query}', data=image_bytes, headers=head)
            result = json.loads(result.text)
            if result["code"] == -300: 
                # TODO qps limit retry
                # https://www.textin.com/document/text_auto_removal
                # retry
                logging.error(
                            f"request {self.url}?{url_query} error, code: {result['code']}. will retry..."
                        )
                time.sleep(3)
                result = requests.post(f'{self.url}?{url_query}', data=image_bytes, headers=head)
                result = json.loads(result.text)

            if result["code"] != 200:
                raise RuntimeError('擦除手写痕迹失败')
            image_data = result["result"]["image"]
            file_key, app_id = upload_image_data(image_data, cacheable=True, file_key_only=True)                     
            oss_key_file = f"{file_key}@{app_id}"
            cache_client.set(key, oss_key_file)
            
            return True, {"busi_type": "agent_message_hand_written_erase", "role": "assistant","content": [{"type": "image_url", "image_url": { "url": f"oss:{oss_key_file}"}}]}

    
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
