
from dataclasses import asdict, dataclass
from typing import Dict, List

from .cstore_oss_factory import CstoreOssFactory
from .abstract_oss_base import AbstractOss


class Osss:
    _default: "Osss"

    @staticmethod
    def default():
        return Osss._default
    

    @staticmethod
    def buildDefault(config: "OsssConfig") -> "Osss":
        Osss._default = Osss(config)


    def __init__(self, config: "OsssConfig") -> None:
        self._config = config
        self._oss_map: Dict[str, AbstractOss] = {}        
        #build oss
        for oss_config in self._config.oss_list:
            oss = oss_config.buildOss()
            self._oss_map[oss_config.app_id] = oss
            if oss_config.is_default:
                self._default_oss = oss


    def defaultOss(self) -> AbstractOss:        
        return self._default_oss


    def getOss(self, app_id: str) -> AbstractOss:
        return self._oss_map.get(app_id, None)


@dataclass
class OsssConfig:
    oss_list: List["OssConfig"]
    
    def dict(self):
        result = asdict(self)
        return result


@dataclass
class OssConfig:
    app_id: str
    base_url: str
    key_prefix: str
    oss_type: str
    is_default: bool


    def buildOss(self) -> AbstractOss:
        if self.oss_type == "cstore":
            return CstoreOssFactory.create(self.app_id, self.base_url, self.key_prefix)
        # TODO other oss type

    def dict(self):
        result = asdict(self)
        return result
