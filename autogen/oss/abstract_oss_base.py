

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Protocol, Tuple


class AbstractOss(Protocol):

    @property
    def app_id(self) -> str:
        ...

    @property
    def key_prefix(self) -> str:
        ...

    def get_download_url(self, file_key: str, expire_seconds: int) -> str:
        pass

    async def async_get_download_url(self, file_key: str, expire_seconds: int) -> str:
        ...

    def batch_get_download_url(self, file_keys: List[str], expire_seconds: int) -> str:
        ...

    async def async_batch_get_download_url(self, file_keys: List[str], expire_seconds: int) -> str:
        ...

    def get_inner_download_url(self, file_key: str, expire_seconds: int) -> str:
        ...

    async def async_get_inner_download_url(self, file_key: str, expire_seconds: int) -> str:
        ...

    def batch_get_inner_download_url(self, file_keys: List[str], expire_seconds: int) -> str:
        ...

    async def async_batch_get_inner_download_url(self, file_keys: List[str], expire_seconds: int) -> str:
        ...

    def get_upload_policy(self) -> "UploadPolicy":
        ...

    async def async_get_upload_policy(self) -> "UploadPolicy":
        ...

    def get_internal_upload_policy(self) -> "UploadPolicy":
        ...

    async def async_get_internal_upload_policy(self) -> "UploadPolicy":
        ...

    def upload_file(self, file_key: str, file_data: bytes) -> str:
        ...

    async def async_upload_file(self, file_key: str, file_data: bytes) -> str:
        ...


@dataclass
class UploadPolicy(object):
    upload_url: str
    method: str
    form_fields: Dict[str, Any]
    header_fields: Dict[str, Any]
    app_id: str
    file_key: str

    def dict(self):
        result = asdict(self)
        return result