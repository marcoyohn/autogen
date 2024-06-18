import json
import os
import time
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
import autogen
from autogen.agentchat.agent import Agent
from autogen.agentchat.contrib.img_utils import get_image_data
from autogen.cache.cache import Cache
from autogen.oai.openai_utils import get_key
from util.send_sign_http import send_request


class ExamAutomaticBoxAgent(autogen.AssistantAgent):
    def __init__(self, message_processor=None, context=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.message_processor = message_processor        
        self.context = context
        self.register_reply(Agent, ExamAutomaticBoxAgent._generate_automatic_box_reply)

    def _generate_automatic_box_reply(
        self,
        messages: Optional[List[Dict]] = None,
        sender: Optional[Agent] = None,
        config: Optional[Any] = None,
    ) -> Tuple[bool, Union[str, Dict, None]]:
        message = messages[-1]
        image_url_dict = message["content"][0]["image_url"]
        filekey = image_url_dict.get("filekey", None) or image_url_dict["url"]
        image = self.context[f"image:{filekey}"]
        img_base64 = get_image_data(image, use_b64=True)
        
        # 获取当前时间（东8区）
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())
        body_params = {
                "image_base64":f"{img_base64}",  
                "anchor":[0,0],
                "type": 1
            }
        
        cache_client = Cache.disk("cache_seed", ".cache")
        key = get_key(body_params)

        response: str = cache_client.get(key, None)
        if response:
            return True, response

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
        return True, response
    
        # TODO mock result
        # return True, json.dumps({
        #     "automatic_box_items":[
        #         {
        #             "item_position": [[65,92],[766,92],[766,376],[65,376]],
        #             "item_position_show":[[65,97],[766,97],[766,371],[65,371]]
        #         },
        #         {
        #             "item_position": [[67,394],[654,394],[654,567],[67,567]],
        #             "item_position_show":[[65,398],[654,398],[654,563],[65,563]]
        #         },
        #         {
        #             "item_position": [[69,660],[758,660],[758,742],[69,742]],
        #             "item_position_show":[[65,662],[758,662],[758,740],[65,740]]
        #         },
        #         {
        #             "item_position": [[67,742],[761,742],[761,816],[67,816]],
        #             "item_position_show":[[65,744],[761,744],[761,815],[65,815]]
        #         }
        #     ]
        # })
    
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
