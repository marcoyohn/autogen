

import os
import time
from typing import Dict, List
import uuid

import httpx
import jwt
from autogen.oss.abstract_oss_base import AbstractOss, UploadPolicy


class DbOss(AbstractOss):

    def __init__(self, app_id: str, base_url: str, internal_base_url: str, key_prefix: str) -> None:
        self._app_id = app_id
        self._base_url = base_url
        self._key_prefix = key_prefix
        self._upload_url = f"{base_url}/api/db-oss/upload"
        self._download_url = f"{base_url}/api/db-oss/download"
        self._internal_upload_url = f"{internal_base_url}/api/db-oss/internal-upload"
        self._internal_download_url = f"{internal_base_url}/api/db-oss/internal-download"
        
    @property
    def app_id(self) -> str:
        return self._app_id

    @property
    def key_prefix(self) -> str:
        return self._key_prefix

    def get_download_url(self, file_key: str, expire_seconds: int) -> str:
        payload = {"op": "download","key": file_key, "app_id": self._app_id, "exp": int(time.time()) + expire_seconds}
        sign = jwt.encode(payload, os.environ["WS_TOKEN_JWT_SECRET"], algorithm=os.environ["WS_TOKEN_JWT_ALGORITHM"])
        return f"{self._download_url}?key={file_key}&app_id={self._app_id}&sign={sign}" 



    async def async_get_download_url(self, file_key: str, expire_seconds: int) -> str:
        return self.get_download_url(file_key, expire_seconds)


    def batch_get_download_url(self, file_keys: List[str], expire_seconds: int) -> str:
        ...

    async def async_batch_get_download_url(self, file_keys: List[str], expire_seconds: int) -> str:
        ...

    def get_inner_download_url(self, file_key: str, expire_seconds: int) -> str:
        payload = {"op": "internal_download","key": file_key, "app_id": self._app_id, "exp": int(time.time()) + expire_seconds}
        sign = jwt.encode(payload, os.environ["WS_TOKEN_JWT_SECRET"], algorithm=os.environ["WS_TOKEN_JWT_ALGORITHM"])
        return f"{self._internal_download_url}?key={file_key}&app_id={self._app_id}&sign={sign}" 

    async def async_get_inner_download_url(self, file_key: str, expire_seconds: int) -> str:
        return self.get_inner_download_url(file_key, expire_seconds)

    def batch_get_inner_download_url(self, file_keys: List[str], expire_seconds: int) -> str:
        ...

    async def async_batch_get_inner_download_url(self, file_keys: List[str], expire_seconds: int) -> str:
        ...

    def get_upload_policy(self) -> "UploadPolicy":        
        file_key = str(uuid.uuid4())
        payload = {"op": "upload", "app_id": self._app_id, "exp": int(time.time()) + 300}
        sign = jwt.encode(payload, os.environ["WS_TOKEN_JWT_SECRET"], algorithm=os.environ["WS_TOKEN_JWT_ALGORITHM"])
        form_fields = {"sign": sign, "key": file_key, "app_id": self._app_id}
        
        return UploadPolicy(upload_url=self._upload_url, method="POST", form_fields=form_fields, header_fields={}, app_id=self._app_id, file_key=file_key)
    

    async def async_get_upload_policy(self) -> "UploadPolicy":
        return self.get_upload_policy()


    def get_internal_upload_policy(self) -> "UploadPolicy":
        file_key = str(uuid.uuid4())
        payload = {"op": "internal_upload", "app_id": self._app_id, "exp": int(time.time()) + 300}
        sign = jwt.encode(payload, os.environ["WS_TOKEN_JWT_SECRET"], algorithm=os.environ["WS_TOKEN_JWT_ALGORITHM"])
        form_fields = {"sign": sign, "key": file_key, "app_id": self._app_id}
                
        return UploadPolicy(upload_url=self._internal_upload_url, method="POST", form_fields=form_fields, header_fields={}, app_id=self._app_id, file_key=file_key)
    

    async def async_get_internal_upload_policy(self) -> "UploadPolicy":
        return self.get_internal_upload_policy()


    def upload_file(self, file_key: str, file_data: bytes) -> str:
        policy = self.get_internal_upload_policy()
        real_file_key = self._key_prefix + file_key
        response = httpx.request(
            policy.method,
            policy.upload_url,
            data={**policy.form_fields, "key": real_file_key},
            files={"file": file_data},
            timeout=60.0,
            # headers={"Content-Type": "multipart/form-data"}  不需要加这个，加了会报错
        )
        response.raise_for_status() 
        return real_file_key


    async def async_upload_file(self, file_key: str, file_data: bytes) -> str:
        async with httpx.AsyncClient() as client:                    
            policy = await self.async_get_internal_upload_policy()
            real_file_key = self._key_prefix + file_key
            response = await client.request(
                policy.method,
                policy.upload_url,
                data={**policy.form_fields, "key": real_file_key},
                files={"file": file_data},
                timeout=60.0,
                # headers={"Content-Type": "multipart/form-data"}  不需要加这个，加了会报错
            )
            response.raise_for_status() 
            return real_file_key