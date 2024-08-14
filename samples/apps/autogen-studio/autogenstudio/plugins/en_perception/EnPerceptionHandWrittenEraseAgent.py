import base64
from io import BytesIO
import json
import logging
import os
import sys
import time
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import requests
import autogen
from autogen.agentchat.agent import Agent
from autogen.agentchat.contrib.img_utils import convert_base64_to_data_uri, get_image_data
from autogen.cache.cache import Cache
from autogen.oai.openai_utils import get_key

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from utils.user_message import resolve_user_image


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
        image = resolve_user_image(message, self.context)     
        buffered = BytesIO()
        image.save(buffered, format="PNG")
        image_bytes = buffered.getvalue()
        image_base64 = base64.b64encode(image_bytes).decode("utf-8")   

        with Cache.disk("tal_automatic_box", ".cache") as cache_client:
            url_query = "dewarp=0&binarization=1"
            key = get_key({"url_query": url_query, "image_base64": image_base64})
            image_data: str = cache_client.get(key, None)
            if image_data:
                return True, {"role": "assistant","content": json.dumps({"msg_type": "agent_message_hand_written_erase", "image_url": { "url": convert_base64_to_data_uri(image_data)}})}
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
            cache_client.set(key, image_data)
            return True, {"role": "assistant","content": json.dumps({"msg_type": "agent_message_hand_written_erase", "image_url": { "url": convert_base64_to_data_uri(image_data)}})}

    
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
