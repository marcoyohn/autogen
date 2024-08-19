
import threading
from typing import Protocol

from autogen.oss.abstract_oss_factory_base import AbstractOssFactory

from .db_oss import DbOss

class DbOssFactory(AbstractOssFactory):

    def create(app_id: str, base_url: str, internal_base_url: str, key_prefix: str) -> DbOss:
        return DbOss(app_id, base_url, internal_base_url, key_prefix)