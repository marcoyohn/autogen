

from typing import Dict, List

import httpx
from .abstract_oss_base import AbstractOss, UploadPolicy


class CstoreOss(AbstractOss):

    def __init__(self, app_id: str, base_url: str, key_prefix: str) -> None:
        self._app_id = app_id
        self._base_url = base_url
        self._key_prefix = key_prefix
        self._upload_policy_url = f"{base_url}/cstore/api/v2/uploadPolicy"
        self._download_url = f"{base_url}/cstore/api/v2/downloadUrl"
        self._internal_upload_policy_url = f"{base_url}/cstore/api/v3/internal-upload-policy"
        self._internal_download_url = f"{base_url}/cstore/api/v3/internal-download-url"
        
    
    def app_id(self) -> str:
        return self._app_id

    def key_prefix(self) -> str:
        return self._key_prefix

    def get_download_url(self, file_key: str, expire_seconds: int) -> str:
        response = httpx.post(
            f"{self._download_url}?appId={self._app_id}&expireSeconds={expire_seconds}",
            json=[file_key],
            headers={"Content-Type": "application/json"}  
        )
        response.raise_for_status() 
        result = response.json()
        if result["code"] != 0:
            raise RuntimeError("获取文件下载地址异常")
        data = result["data"]
        if len(data) == 0:
            return ""
        return data[0]["downloadUrl"]


    async def async_get_download_url(self, file_key: str, expire_seconds: int) -> str:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self._download_url}?appId={self._app_id}&expireSeconds={expire_seconds}",
                json=[file_key],
                headers={"Content-Type": "application/json"}  
            )
            response.raise_for_status() 
            result = response.json()
            if result["code"] != 0:
                raise RuntimeError("获取文件下载地址异常")
            data = result["data"]
            if len(data) == 0:
                return ""
            return data[0]["downloadUrl"]


    def batch_get_download_url(self, file_keys: List[str], expire_seconds: int) -> str:
        ...

    async def async_batch_get_download_url(self, file_keys: List[str], expire_seconds: int) -> str:
        ...

    def get_inner_download_url(self, file_key: str, expire_seconds: int) -> str:
        response = httpx.post(
            self._internal_download_url,
            json={"internal": True, "appId": self._app_id, "srcFileKeyList": [file_key]},
            headers={"Content-Type": "application/json"}  
        )
        response.raise_for_status() 
        result = response.json()
        if result["code"] != 0:
            raise RuntimeError("获取文件下载地址异常")
        return result["data"]["fileKeyToUrlMap"].get(file_key, None)

    async def async_get_inner_download_url(self, file_key: str, expire_seconds: int) -> str:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self._internal_download_url,
                json={"internal": True, "appId": self._app_id, "srcFileKeyList": [file_key]},
                headers={"Content-Type": "application/json"}  
            )
            response.raise_for_status() 
            result = response.json()
            if result["code"] != 0:
                raise RuntimeError("获取文件下载地址异常")
            return result["data"]["fileKeyToUrlMap"].get(file_key, None)

    def batch_get_inner_download_url(self, file_keys: List[str], expire_seconds: int) -> str:
        ...

    async def async_batch_get_inner_download_url(self, file_keys: List[str], expire_seconds: int) -> str:
        ...

    def get_upload_policy(self) -> "UploadPolicy":
        response = httpx.get(
            f"{self._upload_policy_url}?appId={self._app_id}",
            headers={"Content-Type": "application/json"}  
        )
        response.raise_for_status() 
        result = response.json()
        if result["code"] != 0:
            raise RuntimeError("获取文件下载地址异常")
        data: Dict[str, any] = result["data"]
        data_policy: Dict[str, any] = data["policyList"][0]
        file_key = None
        form_fields = {}
        for form_field in data_policy.get("formFields", None):
            k = form_field["key"]
            v = form_field["value"]
            if k == "key":
                file_key = v
            else:
                form_fields[k] =v 
        # TODO header
                
        return UploadPolicy(upload_url=data_policy["uploadUrl"], method="POST", form_fields=form_fields, header_fields={}, app_id=self._app_id, file_key=file_key)
    

    async def async_get_upload_policy(self) -> "UploadPolicy":
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self._upload_policy_url}?appId={self._app_id}",
                headers={"Content-Type": "application/json"}  
            )
            response.raise_for_status() 
            result = response.json()
            if result["code"] != 0:
                raise RuntimeError("获取文件下载地址异常")
            data: Dict[str, any] = result["data"]
            data_policy: Dict[str, any] = data["policyList"][0]
            file_key = None
            form_fields = {}
            for form_field in data_policy.get("formFields", None):
                k = form_field["key"]
                v = form_field["value"]
                if k == "key":
                    file_key = v
                else:
                    form_fields[k] =v 
            # TODO header
                    
            return UploadPolicy(upload_url=data_policy["uploadUrl"], method="POST", form_fields=form_fields, header_fields={}, app_id=self._app_id, file_key=file_key)
        


    def get_internal_upload_policy(self) -> "UploadPolicy":
        response = httpx.post(
            self._internal_upload_policy_url,
            json={"internal": True, "appId": self._app_id},
            headers={"Content-Type": "application/json"}  
        )
        response.raise_for_status() 
        result = response.json()
        if result["code"] != 0:
            raise RuntimeError("获取文件下载地址异常")
        data: Dict[str, any] = result["data"][0]
        
        file_key = None
        form_fields = {}
        for form_field in data.get("formFields", None):
            k = form_field["name"]
            v = form_field["value"]
            if k == "key":
                file_key = v
            else:
                form_fields[k] =v 
        # TODO header
                
        return UploadPolicy(upload_url=data["uploadUrl"], method=data["httpMethod"], form_fields=form_fields, header_fields={}, app_id=self._app_id, file_key=file_key)
    

    async def async_get_internal_upload_policy(self) -> "UploadPolicy":
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self._internal_upload_policy_url,
                json={"internal": True, "appId": self._app_id},
                headers={"Content-Type": "application/json"}  
            )            
            response.raise_for_status() 
            result = response.json()
            if result["code"] != 0:
                raise RuntimeError("获取文件下载地址异常")
            data: Dict[str, any] = result["data"][0]
            
            file_key = None
            form_fields = {}
            for form_field in data.get("formFields", None):
                k = form_field["name"]
                v = form_field["value"]
                if k == "key":
                    file_key = v
                else:
                    form_fields[k] =v 
            # TODO header
                    
            return UploadPolicy(upload_url=data["uploadUrl"], method=data["httpMethod"], form_fields=form_fields, header_fields={}, app_id=self._app_id, file_key=file_key)
        

    def upload_file(self, file_key: str, file_data: bytes) -> str:
        policy = self.get_internal_upload_policy()
        real_file_key = self._key_prefix + file_key
        response = httpx.request(
            policy.method,
            policy.upload_url,
            data={**policy.form_fields, "key": real_file_key},
            files={"file": file_data},
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
                # headers={"Content-Type": "multipart/form-data"}  不需要加这个，加了会报错
            )
            response.raise_for_status() 
            return real_file_key