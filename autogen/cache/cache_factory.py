import logging
import os
from sqlite3 import DatabaseError
import threading
from typing import Any, Dict, Optional, Union

from .abstract_cache_base import AbstractCache
from .disk_cache import DiskCache


class CacheFactory:
    __cache_map = {}
    # 创建互斥锁
    __cache_lock = threading.Lock()

    @staticmethod
    def cache_factory(
        seed: Union[str, int],
        redis_url: Optional[str] = None,
        cache_path_root: str = ".cache",
        cosmosdb_config: Optional[Dict[str, Any]] = None,
    ) -> AbstractCache:
        """
        Factory function for creating cache instances.

        This function decides whether to create a RedisCache, DiskCache, or CosmosDBCache instance
        based on the provided parameters. If RedisCache is available and a redis_url is provided,
        a RedisCache instance is created. If connection_string, database_id, and container_id
        are provided, a CosmosDBCache is created. Otherwise, a DiskCache instance is used.

        Args:
            seed (Union[str, int]): Used as a seed or namespace for the cache.
            redis_url (Optional[str]): URL for the Redis server.
            cache_path_root (str): Root path for the disk cache.
            cosmosdb_config (Optional[Dict[str, str]]): Dictionary containing 'connection_string',
                                                       'database_id', and 'container_id' for Cosmos DB cache.

        Returns:
            An instance of RedisCache, DiskCache, or CosmosDBCache.

        Examples:

        Creating a Redis cache

        ```python
        redis_cache = cache_factory("myseed", "redis://localhost:6379/0")
        ```
        Creating a Disk cache

        ```python
        disk_cache = cache_factory("myseed", None)
        ```

        Creating a Cosmos DB cache:
        ```python
        cosmos_cache = cache_factory("myseed", cosmosdb_config={
                "connection_string": "your_connection_string",
                "database_id": "your_database_id",
                "container_id": "your_container_id"}
            )
        ```

        """
        if redis_url:
            try:
                from .redis_cache import RedisCache
                cache = CacheFactory.__cache_map.get("redis:" + seed, None)
                if not cache:
                    cache = RedisCache(seed, redis_url)
                    CacheFactory.__cache_map["redis:" + seed] = cache
                return cache
            except ImportError:
                logging.warning(
                    "RedisCache is not available. Checking other cache options. The last fallback is DiskCache."
                )

        if cosmosdb_config:
            try:
                from .cosmos_db_cache import CosmosDBCache
                cache = CacheFactory.__cache_map.get("cosmos:" + seed, None)
                if not cache:
                    cache = CosmosDBCache.create_cache(seed, cosmosdb_config)
                    CacheFactory.__cache_map["cosmos:" + seed] = cache
                return cache
            except ImportError:
                logging.warning("CosmosDBCache is not available. Fallback to DiskCache.")

        # Default to DiskCache if neither Redis nor Cosmos DB configurations are provided
        path = os.path.join(cache_path_root, str(seed))
        # modify by ymc
        cache = CacheFactory.__cache_map.get("disk:" + path, None)
        if not cache:
            # 上锁
            CacheFactory.__cache_lock.acquire()
            try:
                # 再次检查cache是否已经被创建
                cache = CacheFactory.__cache_map.get("disk:" + path, None)
                if not cache:
                    cache = DiskCache(os.path.join(os.environ.get("AUTOGEN_CACHE_DIR") or ".", path))
                    CacheFactory.__cache_map["disk:" + path] = cache
            finally:
                # 释放锁
                CacheFactory.__cache_lock.release()        
            
        return cache
        
        
