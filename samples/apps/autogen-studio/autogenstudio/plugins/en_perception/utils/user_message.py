

from typing import Dict, List
from PIL import Image

from autogen.agentchat.contrib.img_utils import convert_base64_to_data_uri, get_image_data, get_pil_image, pil_to_data_uri
from autogen.cache.cache import Cache


def resolve_user_image_date_uri(message: Dict, context: Dict) -> str:
    # content 格式  
    # {
    # 	"type": "image_url", "image_url": {"url": "https://xxx", "filekey": "xxx", "sprite": [xx,xx,xx,xx], "context_key": ""}
    # } 
    images: List[Dict] = [item for item in message["content"] if item["type"] == "image_url"]
    images_len = len(images)
    if images_len == 0:
        raise RuntimeError('请输入一张图片')
    if images_len > 1:
        raise RuntimeError('输入只支持一张图片')
    image_url_dict = images[0]["image_url"]
    image_url = image_url_dict["url"]
    image_context_key = image_url_dict.get("context_key", None)
    filekey = image_url_dict.get("filekey", None) or image_url
    image = None
    if image_context_key:
        image = context[image_context_key]
    if image is None:
        with Cache.disk("user_message_img", ".cache") as cache_client:
            image_cache: str = cache_client.get(filekey, None)
            if image_cache:
                image_data_uri = convert_base64_to_data_uri(image_cache)
            else:
                image_data = get_image_data(image_url, use_b64=True)
                image_data_uri = convert_base64_to_data_uri(image_data)
                cache_client.set(filekey, image_data)
    else:
        image_data_uri = pil_to_data_uri(get_pil_image(image))

    return image_data_uri

def resolve_user_image_date(message: Dict, context: Dict) -> str:
    # content 格式  
    # {
    # 	"type": "image_url", "image_url": {"url": "https://xxx", "filekey": "xxx", "sprite": [xx,xx,xx,xx], "context_key": ""}
    # } 
    images: List[Dict] = [item for item in message["content"] if item["type"] == "image_url"]
    images_len = len(images)
    if images_len == 0:
        raise RuntimeError('请输入一张图片')
    if images_len > 1:
        raise RuntimeError('输入只支持一张图片')
    image_url_dict = images[0]["image_url"]
    image_url = image_url_dict["url"]
    image_context_key = image_url_dict.get("context_key", None)
    filekey = image_url_dict.get("filekey", None) or image_url
    image = None
    if image_context_key:
        image = context[image_context_key]
    if image is None:
        with Cache.disk("user_message_img", ".cache") as cache_client:
            image_cache: str = cache_client.get(filekey, None)
            if image_cache:
                image_data = get_image_data(image_cache, use_b64=True)
            else:
                image_data = get_image_data(image_url, use_b64=True)
                cache_client.set(filekey, image_data)                
    else:
        image_data = get_image_data(image, use_b64=True)

    return image_data

def resolve_user_image(message: Dict, context: Dict) -> Image.Image:
    # content 格式  
    # {
    # 	"type": "image_url", "image_url": {"url": "https://xxx", "filekey": "xxx", "sprite": [xx,xx,xx,xx], "context_key": ""}
    # } 
    images: List[Dict] = [item for item in message["content"] if item["type"] == "image_url"]
    images_len = len(images)
    if images_len == 0:
        raise RuntimeError('请输入一张图片')
    if images_len > 1:
        raise RuntimeError('输入只支持一张图片')
    image_url_dict = images[0]["image_url"]
    image_url = image_url_dict["url"]
    image_context_key = image_url_dict.get("context_key", None)
    filekey = image_url_dict.get("filekey", None) or image_url
    image = None
    if image_context_key:
        image = context[image_context_key]
    if image is None:
        with Cache.disk("user_message_img", ".cache") as cache_client:
            image_cache: str = cache_client.get(filekey, None)
            if image_cache:
                pil_image = get_pil_image(image_cache)
            else:
                pil_image = get_pil_image(image_url)
                cache_client.set(filekey, get_image_data(pil_image, use_b64=True))                
    else:
        pil_image = get_pil_image(image)

    return pil_image

def replace_user_image_from_context(image_url_dict: Dict, context: Dict) -> Dict:   
    image_url = image_url_dict["url"]
    image_context_key = image_url_dict.get("context_key", None)
    filekey = image_url_dict.get("filekey", None) or image_url
    image = None
    if image_context_key:
        image = context[image_context_key]
    if image is None:
        with Cache.disk("user_message_img", ".cache") as cache_client:
            image_cache: str = cache_client.get(filekey, None)
            if image_cache:
                image_data_uri = convert_base64_to_data_uri(image_cache)
            else:
                image_data = get_image_data(image_url, use_b64=True)
                image_data_uri = convert_base64_to_data_uri(image_data)
                cache_client.set(filekey, image_data)
    else:
        image_data_uri = pil_to_data_uri(get_pil_image(image))

    return {**image_url_dict, "url": image_data_uri}