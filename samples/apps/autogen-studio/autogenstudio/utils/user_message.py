

import base64
from io import BytesIO
import re
from typing import Any, Dict, List, Optional, Tuple, Union
from PIL import Image
import requests

from autogen.agentchat.contrib.img_utils import convert_base64_to_data_uri, get_image_data, get_pil_image, pil_to_data_uri
from autogen.cache.cache import Cache
from autogen.oss.oss_utils import download_oss_file, upload_image_data

def ensure_user_image_oss(content: Union[str, List[Dict]], context: Dict[str, Any]):
    if isinstance(content, str):
        return
    images: List[Dict] = [item for item in content if item["type"] == "image_url"]
    if len(images) == 0:
        return
    for image in images:
        image = image["image_url"]
        image_data: str = image["url"]
        if image_data.startswith("oss:"):
            continue
        if image_data.startswith("http://") or image_data.startswith("https://"):
            # A URL file
            response = requests.get(image_data)
            image_data = response.content
            image["url_origin_format"] = "url"
        elif re.match(r"data:image/(?:png|jpeg);base64,", image_data):
            # A URI. Remove the prefix and decode the base64 string.
            image_data = re.sub(r"data:image/(?:png|jpeg);base64,", "", image_data)
            image_data = base64.b64decode(image_data)    
            image["url_origin_format"] = "data_uri"    
        else:
            # base64 encoded string
            image_data = base64.b64decode(image_data)
            image["url_origin_format"] = "base64"
        file_key, app_id  = upload_image_data(image_data, cacheable=True, file_key_only=True) 
        image["url"] = f"oss:{file_key}@{app_id}"
        context[f"image_bytes_{file_key}@{app_id}"] = image_data         

def ensure_get_user_image_oss_key_and_crop(message: Dict) -> Tuple[str,List[int]]:
    # content 格式  
    # {
    # 	"type": "image_url", "image_url": {"url": "oss:", "crop": [xx,xx,xx,xx]}
    # } 
    images: List[Dict] = [item for item in message["content"] if item["type"] == "image_url"]
    images_len = len(images)
    if images_len == 0:
        raise RuntimeError('请输入一张图片')
    if images_len > 1:
        raise RuntimeError('输入只支持一张图片')
    image_url: Dict = images[0]["image_url"]
    url: str = image_url["url"]
    if not url.startswith("oss:"):
        raise RuntimeError('图片url非oss格式')
    return (url[4:],image_url.get("crop", None))

def resolve_user_image_date_uri(oss_key: str, context: Dict[str, Any], crop: List[int]=None) -> str:    
    image_base64 = resolve_user_image_base64(oss_key, context, crop=crop)
    return convert_base64_to_data_uri(image_base64)
    

def resolve_user_image_base64(oss_key: str, context: Dict[str, Any], crop: List[int]=None) -> str:
    image_bytes = resolve_user_image_bytes(oss_key, context, crop=crop)    
    return base64.b64encode(image_bytes).decode("utf-8")

def resolve_user_image_bytes(oss_key: str, context: Dict[str, Any], crop: List[int]=None) -> bytes:
    image_bytes = context.get(f"image_bytes_{oss_key}", None)
    if image_bytes is None:
        image_bytes = download_oss_file(oss_key)
        context[f"image_bytes_{oss_key}"] = image_bytes
    if crop and len(crop) > 0:
        if len(crop) == 8:
            image = Image.open(BytesIO(image_bytes)).crop((crop[0],crop[1],crop[4],crop[5]))
        else:
            image = Image.open(BytesIO(image_bytes)).crop(tuple(crop))
        buffered = BytesIO()
        image.save(buffered, format="PNG")
        image_bytes = buffered.getvalue()
    return image_bytes

def try_get_from_context(content: Union[str, List[Dict]], context: Dict[str, Any]) -> Optional[Any]:
    # content 格式  
    # {
    # 	"type": "context", "context": "{context_key}"
    # } 
    if isinstance(content, str):
        return None
    context_keys: List[Dict] = [item["context"] for item in content if item["type"] == "context"]
    context_len = len(context_keys)
    if context_len == 0:
        return None
    if context_len > 1:
        raise RuntimeError('只支持传递一个context')
    return context.get(context_keys[0], None)