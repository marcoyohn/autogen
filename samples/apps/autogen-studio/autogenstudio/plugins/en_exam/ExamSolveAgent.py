import copy
import json
from typing import Any, Callable, Dict, List, Literal, Optional, Tuple, Union
import autogen
from autogen.agentchat.agent import Agent
from autogen.agentchat.contrib.img_utils import get_image_data
from autogen.agentchat.conversable_agent import ConversableAgent
from autogen._pydantic import model_dump

ExamSolveTypeSymbol = Literal["solve", "math_expr"]

class ExamSolveAgent(autogen.AssistantAgent):
    def __init__(self, message_processor=None, context=None, exam_solve_type: ExamSolveTypeSymbol=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.message_processor = message_processor     
        self.context = context   
        self.exam_solve_type = exam_solve_type
        # Override the `generate_oai_reply`
        self.replace_reply_func(ConversableAgent.generate_oai_reply, ExamSolveAgent.generate_oai_reply)
        self.replace_reply_func(
            ConversableAgent.a_generate_oai_reply,
            ExamSolveAgent.a_generate_oai_reply,
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
        
        automatic_box_item_sprite = None
        automatic_box_item = {}
        result = {"msg_type": f"agent_message_{self.exam_solve_type}_patch", "automatic_box_items":[automatic_box_item]}
        new_messages = []
        for message in messages:
            if isinstance(message, dict) and "content" in message and isinstance(message["content"], list):
                message = copy.deepcopy(message)
                for item in message["content"]:
                    if isinstance(item, dict) and "image_url" in item:
                        image_url_dict = item["image_url"]
                        filekey = image_url_dict.get("filekey", None) or image_url_dict["url"]
                        sprite = image_url_dict["sprite"]
                        automatic_box_item_sprite = sprite
                        cropped_image = self.context[f"image:{filekey}:{sprite[0]}-{sprite[1]}-{sprite[2]}-{sprite[3]}"]
                        cropped_image_base64 = get_image_data(cropped_image, use_b64=True)
                        image_url_dict["url"] = f"data:image/png;base64,{cropped_image_base64}"

            new_messages.append(message)
        

        messages_with_b64_img = self._oai_system_message + new_messages

        # TODO: #1143 handle token limit exceeded error
        response = client.create(context=messages[-1].pop("context", None), messages=messages_with_b64_img)

        # TODO: line 301, line 271 is converting messages to dict. Can be removed after ChatCompletionMessage_to_dict is merged.
        extracted_response = client.extract_text_or_completion_object(response)[0]
        if not isinstance(extracted_response, str):
            extracted_response = model_dump(extracted_response)

        context_result = self.context["result"]
        for box_item in context_result["automatic_box_items"]:
            positions = box_item["item_position_show"]
            if automatic_box_item_sprite[0] == positions[0][0] and automatic_box_item_sprite[1] == positions[0][1] and automatic_box_item_sprite[2] == positions[2][0] and automatic_box_item_sprite[3] == positions[2][1]:
                automatic_box_item["item_index"] = box_item["item_index"]
                box_item[self.exam_solve_type] = extracted_response
                break

        automatic_box_item[self.exam_solve_type] = extracted_response

        return True, json.dumps(result, ensure_ascii=False)


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
