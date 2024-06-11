import json
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
import autogen
from autogen.agentchat.agent import Agent


class ExamAutomaticBoxAgent(autogen.AssistantAgent):
    def __init__(self, message_processor=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.message_processor = message_processor        

        self.register_reply(Agent, ExamAutomaticBoxAgent._generate_automatic_box_reply)

    def _generate_automatic_box_reply(
        self,
        messages: Optional[List[Dict]] = None,
        sender: Optional[Agent] = None,
        config: Optional[Any] = None,
    ) -> Tuple[bool, Union[str, Dict, None]]:
        # call third part

        # TODO mock result
        return True, json.dumps({
            "automatic_box_items":[
                {
                    "item_position": [[65,92],[766,92],[766,376],[65,376]],
                    "item_position_show":[[65,97],[766,97],[766,371],[65,371]]
                },
                {
                    "item_position": [[67,394],[654,394],[654,567],[67,567]],
                    "item_position_show":[[65,398],[654,398],[654,563],[65,563]]
                },
                {
                    "item_position": [[69,660],[758,660],[758,742],[69,742]],
                    "item_position_show":[[65,662],[758,662],[758,740],[65,740]]
                },
                {
                    "item_position": [[67,742],[761,742],[761,816],[67,816]],
                    "item_position_show":[[65,744],[761,744],[761,815],[65,815]]
                }
            ]
        })
    
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
