
import threading
from typing import Protocol

from .cstore_oss import CstoreOss

from .abstract_oss_factory_base import AbstractOssFactory


class CstoreOssFactory(AbstractOssFactory):

    def create(app_id: str, base_url: str, key_prefix: str) -> CstoreOss:
        return CstoreOss(app_id, base_url, key_prefix)