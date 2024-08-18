
import base64
import hashlib
import re
from typing import Optional, Tuple, Union
from uuid import uuid4

import httpx

from autogen.agentchat.contrib.img_utils import get_image_suffix
from autogen.cache.cache import Cache
from autogen.oai.openai_utils import get_key
from autogen.oss.Osss import OssConfig, Osss, OsssConfig


def upload_image_data(image_data: Union[str,bytes], cacheable: Optional[bool] = True, cache_name: Optional[str] = None, file_key_only: Optional[bool]=False) -> Union[Tuple[str, str], Tuple[str, str, str]]:
    if isinstance(image_data, str): 
        if re.match(r"data:image/(?:png|jpeg);base64,", image_data):
            # A URI. Remove the prefix and decode the base64 string.
            image_data = re.sub(r"data:image/(?:png|jpeg);base64,", "", image_data)
        image_data_bytes = base64.b64decode(image_data)
    else:
        image_data_bytes = image_data
    if cacheable:
        with Cache.disk(cache_name or "oss_upload", ".cache") as cache_client:
            key = hashlib.md5(image_data_bytes).hexdigest() + str(len(image_data_bytes)) + str(image_data_bytes[-10:])
            oss_key_file: str = cache_client.get(key, None)
            if oss_key_file:
                file_key, app_id = oss_key_file.split("@")
                if file_key_only:
                    return (file_key, app_id)
                url = Osss.default().getOss(app_id).get_download_url(file_key, 3600*24)
                return (file_key, app_id, url)
            else:
                oss = Osss.default().defaultOss()
                file_key = str(uuid4()) + "." + get_image_suffix(image_data_bytes)                                
                file_key = oss.upload_file(file_key, image_data_bytes)
                app_id = oss.app_id
                cache_client.set(key, file_key+"@"+app_id)            
                if file_key_only:
                    return (file_key, app_id)
                url = oss.get_download_url(file_key, 3600*24)                
                return (file_key, app_id, url)
    else:
        oss = Osss.default().defaultOss()
        file_key = uuid4() + "." + get_image_suffix(image_data_bytes)                                
        file_key = oss.upload_file(file_key, image_data_bytes)
        app_id = oss.app_id
        if file_key_only:
            return (file_key, app_id)
        url = oss.get_download_url(file_key, 3600*24)                
        return (file_key, app_id, url)

def download_oss_file(oss_key: str) -> bytes:
    file_key, app_id = oss_key.split("@")
    url = Osss.default().getOss(app_id).get_inner_download_url(file_key, 3600)
    response = httpx.get(url)
    response.raise_for_status() 
    return response.content

if __name__ == "__main__":
    
    def image_to_base64(image_path):
        with open(image_path, "rb") as image_file:
            base64_image = base64.b64encode(image_file.read()).decode('utf-8')
        return base64_image
    
    
    oss_list = []
    # oss_config = OssConfig(app_id="10523", base_url="https://cstore.test.seewo.com", key_prefix="she-agent/", oss_type="cstore", is_default=True)
    oss_config = OssConfig(app_id="10410", base_url="https://cstore.test.seewo.com", key_prefix="she-models/", oss_type="cstore", is_default=True)
    oss_list.append(oss_config)
    osss_config = OsssConfig(oss_list=oss_list)
    Osss.buildDefault(osss_config)
    

    image_data = image_to_base64("/Users/user/code/ai/agent_demo/erase/images/1.jpg")
    file_key, app_id, url  = upload_image_data(image_data, cacheable=True, file_key_only=False) 
    print(file_key)
    print(app_id)
    print(url)
    print(Osss.default().defaultOss().get_inner_download_url(file_key, 3600))
    print(Osss.default().defaultOss().get_download_url(file_key, 3600))
