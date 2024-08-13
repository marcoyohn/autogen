
from typing import Any, Dict, List, Optional, Tuple, Union


import autogen


def function_call_direct_reply(
    self,
    messages: Optional[List[Dict]] = None,
    sender: Optional[autogen.Agent] = None,
    config: Optional[Any] = None,
) -> Tuple[bool, Union[Dict, None]]:
    """
    Generate a reply using function call.

    "function_call" replaced by "tool_calls" as of [OpenAI API v1.1.0](https://github.com/openai/openai-python/releases/tag/v1.1.0)
    See https://platform.openai.com/docs/api-reference/chat/create#chat-create-functions
    """
    if config is None:
        config = self
    if messages is None:
        messages = self._oai_messages[sender]
    message = messages[-1]
    if ("function_call" in message and message["function_call"]) or ("tool_calls" in message and message["tool_calls"]):    
        # 返回空，阻断reply;   
        return True, None
    return False, None