

from dataclasses import dataclass
from autogen.oss.Osss import OssConfig
from autogen.oss.abstract_oss_base import AbstractOss
from .db_oss_factory import DbOssFactory

@dataclass
class DbOssConfig(OssConfig):
    internal_base_url: str

    def buildOss(self) -> AbstractOss:
        return DbOssFactory.create(self.app_id, self.base_url, self.internal_base_url, self.key_prefix)