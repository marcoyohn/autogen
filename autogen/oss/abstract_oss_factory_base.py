
from typing import Protocol

from .abstract_oss_base import AbstractOss


class AbstractOssFactory(Protocol):

    def create(app_id: str, base_url: str) -> AbstractOss:
        ... 