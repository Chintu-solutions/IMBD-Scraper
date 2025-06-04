"""
Enhanced IMDb Scraper - Cache Management
========================================

Redis-based caching system with automatic serialization, TTL management,
and advanced caching patterns for improved performance.

Usage:
    from app.core.cache import cache_manager
    
    # Simple caching
    await cache_manager.set("key", "value", ttl=3600)
    value = await cache_manager.get("key")
    
    # Function caching decorator
    @cache_manager.cached(ttl=300)
    async def expensive_function(param):
        return result
"""

import asyncio
import json
import pickle
import logging
from datetime import datetime, timedelta
from typing import Any, Optional, Union, Dict, List, Callable, TypeVar, Generic
from functools import wraps
import hashlib

import redis.asyncio as redis
from redis.asyncio import Redis
from redis.exceptions import RedisError, ConnectionError

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Type variables for generic caching
T = TypeVar('T')
F = TypeVar('F', bound=Callable[..., Any])

# ==========================================
# REDIS CLIENT CONFIGURATION
# ==========================================

# Global Redis client
redis_client: Optional[Redis] = None


def create_redis_client() -> Redis:
    """Create and configure Redis client"""
    
    logger.info("Creating Redis client...")
    
    try:
        # Parse Redis URL for logging (without password)
        redis_url_parts = settings.REDIS_URL.split('@')
        safe_url = redis_url_parts[-1] if '@' in settings.REDIS_URL else settings.REDIS_URL
        logger.info(f"Connecting to Redis: {safe_url}")
        
        # Create Redis client with configuration
        client = redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=False,  # We handle encoding ourselves
            max_connections=settings.REDIS_MAX_CONNECTIONS,
            retry_on_timeout=settings.REDIS_RETRY_ON_TIMEOUT,
            socket_keepalive=settings.REDIS_SOCKET_KEEPALIVE,
            socket_keepalive_options=settings.REDIS_SOCKET_KEEPALIVE_OPTIONS,
            health_check_interval=30,
        )
        
        logger.info("Redis client created successfully")
        return client
        
    except Exception as e:
        logger.error(f"Failed to create Redis client: {e}")
        raise


async def init_redis() -> None:
    """Initialize Redis connection"""
    global redis_client
    
    try:
        redis_client = create_redis_client()
        
        # Test connection
        await test_redis_connection()
        
        logger.info("Redis initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize Redis: {e}")
        raise


async def close_redis() -> None:
    """Close Redis connection"""
    global redis_client
    
    if redis_client:
        try:
            await redis_client.close()
            logger.info("Redis connection closed")
        except Exception as e:
            logger.error(f"Error closing Redis connection: {e}")
        finally:
            redis_client = None


async def test_redis_connection() -> bool:
    """Test Redis connection"""
    if not redis_client:
        raise RuntimeError("Redis client not initialized")
    
    try:
        await redis_client.ping()
        logger.info("Redis connection test successful")
        return True
    except Exception as e:
        logger.error(f"Redis connection test failed: {e}")
        raise


# ==========================================
# SERIALIZATION UTILITIES
# ==========================================

class CacheSerializer:
    """Handle serialization/deserialization for cache values"""
    
    @staticmethod
    def serialize(value: Any) -> bytes:
        """Serialize value for Redis storage"""
        try:
            if isinstance(value, (str, int, float, bool)):
                # Simple types - use JSON for readability
                return json.dumps(value).encode('utf-8')
            elif isinstance(value, (dict, list, tuple)):
                # JSON-serializable types
                return json.dumps(value).encode('utf-8')
            else:
                # Complex types - use pickle
                return pickle.dumps(value)
        except Exception as e:
            logger.error(f"Failed to serialize value: {e}")
            raise
    
    @staticmethod
    def deserialize(data: bytes) -> Any:
        """Deserialize value from Redis storage"""
        try:
            # Try JSON first (most common case)
            try:
                return json.loads(data.decode('utf-8'))
            except (json.JSONDecodeError, UnicodeDecodeError):
                # Fall back to pickle
                return pickle.loads(data)
        except Exception as e:
            logger.error(f"Failed to deserialize value: {e}")
            raise


# ==========================================
# CACHE KEY MANAGEMENT
# ==========================================

class CacheKeyManager:
    """Manage cache key generation and namespacing"""
    
    def __init__(self, namespace: str = "imdb_scraper"):
        self.namespace = namespace
    
    def make_key(self, *parts: Union[str, int]) -> str:
        """Generate a cache key from parts"""
        key_parts = [self.namespace] + [str(part) for part in parts]
        return ":".join(key_parts)
    
    def make_function_key(self, func_name: str, args: tuple, kwargs: dict) -> str:
        """Generate cache key for function calls"""
        # Create deterministic hash of arguments
        arg_str = str(args) + str(sorted(kwargs.items()))
        arg_hash = hashlib.md5(arg_str.encode()).hexdigest()[:16]
        
        return self.make_key("func", func_name, arg_hash)
    
    def make_pattern(self, *parts: Union[str, int]) -> str:
        """Generate a pattern for key matching"""
        pattern_parts = [self.namespace] + [str(part) for part in parts]
        return ":".join(pattern_parts) + "*"


# ==========================================
# CACHE MANAGER
# ==========================================

class CacheManager:
    """Main cache management class with advanced features"""
    
    def __init__(self, redis_client: Redis, namespace: str = "imdb_scraper"):
        self.redis = redis_client
        self.serializer = CacheSerializer()
        self.key_manager = CacheKeyManager(namespace)
        self.default_ttl = settings.CACHE_DEFAULT_TTL
    
    # ==========================================
    # BASIC OPERATIONS
    # ==========================================
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        try:
            cache_key = self.key_manager.make_key(key)
            data = await self.redis.get(cache_key)
            
            if data is None:
                return None
            
            return self.serializer.deserialize(data)
            
        except RedisError as e:
            logger.error(f"Redis error getting key '{key}': {e}")
            return None
        except Exception as e:
            logger.error(f"Cache error getting key '{key}': {e}")
            return None
    
    async def set(
        self, 
        key: str, 
        value: Any, 
        ttl: Optional[int] = None
    ) -> bool:
        """Set value in cache with optional TTL"""
        try:
            cache_key = self.key_manager.make_key(key)
            data = self.serializer.serialize(value)
            
            if ttl is None:
                ttl = self.default_ttl
            
            result = await self.redis.setex(cache_key, ttl, data)
            return bool(result)
            
        except RedisError as e:
            logger.error(f"Redis error setting key '{key}': {e}")
            return False
        except Exception as e:
            logger.error(f"Cache error setting key '{key}': {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete key from cache"""
        try:
            cache_key = self.key_manager.make_key(key)
            result = await self.redis.delete(cache_key)
            return bool(result)
            
        except RedisError as e:
            logger.error(f"Redis error deleting key '{key}': {e}")
            return False
        except Exception as e:
            logger.error(f"Cache error deleting key '{key}': {e}")
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache"""
        try:
            cache_key = self.key_manager.make_key(key)
            result = await self.redis.exists(cache_key)
            return bool(result)
            
        except RedisError as e:
            logger.error(f"Redis error checking key '{key}': {e}")
            return False
        except Exception as e:
            logger.error(f"Cache error checking key '{key}': {e}")
            return False
    
    async def expire(self, key: str, ttl: int) -> bool:
        """Set TTL for existing key"""
        try:
            cache_key = self.key_manager.make_key(key)
            result = await self.redis.expire(cache_key, ttl)
            return bool(result)
            
        except RedisError as e:
            logger.error(f"Redis error setting TTL for key '{key}': {e}")
            return False
        except Exception as e:
            logger.error(f"Cache error setting TTL for key '{key}': {e}")
            return False
    
    async def ttl(self, key: str) -> int:
        """Get TTL for key"""
        try:
            cache_key = self.key_manager.make_key(key)
            result = await self.redis.ttl(cache_key)
            return result
            
        except RedisError as e:
            logger.error(f"Redis error getting TTL for key '{key}': {e}")
            return -1
        except Exception as e:
            logger.error(f"Cache error getting TTL for key '{key}': {e}")
            return -1
    
    # ==========================================
    # ADVANCED OPERATIONS
    # ==========================================
    
    async def get_many(self, keys: List[str]) -> Dict[str, Any]:
        """Get multiple values from cache"""
        try:
            cache_keys = [self.key_manager.make_key(key) for key in keys]
            
            if not cache_keys:
                return {}
            
            values = await self.redis.mget(cache_keys)
            result = {}
            
            for key, value in zip(keys, values):
                if value is not None:
                    try:
                        result[key] = self.serializer.deserialize(value)
                    except Exception as e:
                        logger.error(f"Failed to deserialize value for key '{key}': {e}")
            
            return result
            
        except RedisError as e:
            logger.error(f"Redis error getting multiple keys: {e}")
            return {}
        except Exception as e:
            logger.error(f"Cache error getting multiple keys: {e}")
            return {}
    
    async def set_many(
        self, 
        mapping: Dict[str, Any], 
        ttl: Optional[int] = None
    ) -> bool:
        """Set multiple values in cache"""
        try:
            if not mapping:
                return True
            
            if ttl is None:
                ttl = self.default_ttl
            
            # Use pipeline for atomic operation
            async with self.redis.pipeline() as pipe:
                for key, value in mapping.items():
                    cache_key = self.key_manager.make_key(key)
                    data = self.serializer.serialize(value)
                    pipe.setex(cache_key, ttl, data)
                
                results = await pipe.execute()
                return all(results)
                
        except RedisError as e:
            logger.error(f"Redis error setting multiple keys: {e}")
            return False
        except Exception as e:
            logger.error(f"Cache error setting multiple keys: {e}")
            return False
    
    async def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern"""
        try:
            cache_pattern = self.key_manager.make_pattern(pattern)
            
            # Get all matching keys
            keys = []
            cursor = 0
            while True:
                cursor, batch_keys = await self.redis.scan(
                    cursor=cursor, 
                    match=cache_pattern, 
                    count=1000
                )
                keys.extend(batch_keys)
                if cursor == 0:
                    break
            
            if not keys:
                return 0
            
            # Delete in batches
            deleted = 0
            batch_size = 1000
            for i in range(0, len(keys), batch_size):
                batch = keys[i:i + batch_size]
                deleted += await self.redis.delete(*batch)
            
            return deleted
            
        except RedisError as e:
            logger.error(f"Redis error deleting pattern '{pattern}': {e}")
            return 0
        except Exception as e:
            logger.error(f"Cache error deleting pattern '{pattern}': {e}")
            return 0
    
    async def clear_namespace(self, namespace: Optional[str] = None) -> int:
        """Clear all keys in namespace"""
        if namespace is None:
            namespace = self.key_manager.namespace
        
        pattern = f"{namespace}:*"
        
        try:
            keys = []
            cursor = 0
            while True:
                cursor, batch_keys = await self.redis.scan(
                    cursor=cursor, 
                    match=pattern, 
                    count=1000
                )
                keys.extend(batch_keys)
                if cursor == 0:
                    break
            
            if not keys:
                return 0
            
            return await self.redis.delete(*keys)
            
        except RedisError as e:
            logger.error(f"Redis error clearing namespace '{namespace}': {e}")
            return 0
        except Exception as e:
            logger.error(f"Cache error clearing namespace '{namespace}': {e}")
            return 0
    
    # ==========================================
    # FUNCTION CACHING DECORATOR
    # ==========================================
    
    def cached(
        self, 
        ttl: Optional[int] = None,
        key_func: Optional[Callable] = None,
        ignore_kwargs: Optional[List[str]] = None
    ):
        """
        Decorator for caching function results
        
        Args:
            ttl: Cache TTL in seconds
            key_func: Custom function to generate cache key
            ignore_kwargs: List of kwargs to ignore when generating cache key
        """
        if ttl is None:
            ttl = self.default_ttl
        
        if ignore_kwargs is None:
            ignore_kwargs = []
        
        def decorator(func: F) -> F:
            @wraps(func)
            async def wrapper(*args, **kwargs):
                # Generate cache key
                if key_func:
                    cache_key = key_func(*args, **kwargs)
                else:
                    # Filter out ignored kwargs
                    filtered_kwargs = {
                        k: v for k, v in kwargs.items() 
                        if k not in ignore_kwargs
                    }
                    cache_key = self.key_manager.make_function_key(
                        func.__name__, args, filtered_kwargs
                    )
                
                # Try to get from cache
                cached_result = await self.get(cache_key)
                if cached_result is not None:
                    logger.debug(f"Cache hit for function '{func.__name__}'")
                    return cached_result
                
                # Execute function
                logger.debug(f"Cache miss for function '{func.__name__}'")
                result = await func(*args, **kwargs)
                
                # Cache result
                await self.set(cache_key, result, ttl)
                
                return result
            
            return wrapper
        
        return decorator
    
    # ==========================================
    # CACHE STATISTICS AND MONITORING
    # ==========================================
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        try:
            info = await self.redis.info()
            
            # Get namespace-specific stats
            namespace_pattern = f"{self.key_manager.namespace}:*"
            namespace_keys = 0
            cursor = 0
            while True:
                cursor, keys = await self.redis.scan(
                    cursor=cursor,
                    match=namespace_pattern,
                    count=1000
                )
                namespace_keys += len(keys)
                if cursor == 0:
                    break
            
            return {
                "redis_info": {
                    "version": info.get("redis_version"),
                    "uptime_seconds": info.get("uptime_in_seconds"),
                    "connected_clients": info.get("connected_clients"),
                    "used_memory": info.get("used_memory_human"),
                    "total_commands_processed": info.get("total_commands_processed"),
                    "instantaneous_ops_per_sec": info.get("instantaneous_ops_per_sec"),
                },
                "namespace_stats": {
                    "namespace": self.key_manager.namespace,
                    "total_keys": namespace_keys,
                },
                "connection_pool": {
                    "created_connections": self.redis.connection_pool.created_connections,
                    "available_connections": len(self.redis.connection_pool._available_connections),
                    "in_use_connections": len(self.redis.connection_pool._in_use_connections),
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get cache stats: {e}")
            return {"error": str(e)}
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform cache health check"""
        health_status = {
            "status": "healthy",
            "checks": {},
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        # Test basic connectivity
        try:
            await self.redis.ping()
            health_status["checks"]["connectivity"] = "pass"
        except Exception as e:
            health_status["status"] = "unhealthy"
            health_status["checks"]["connectivity"] = f"fail: {e}"
        
        # Test read/write operations
        try:
            test_key = f"health_check_{int(asyncio.get_event_loop().time())}"
            test_value = "health_check_value"
            
            await self.set(test_key, test_value, ttl=60)
            retrieved_value = await self.get(test_key)
            await self.delete(test_key)
            
            if retrieved_value == test_value:
                health_status["checks"]["read_write"] = "pass"
            else:
                health_status["status"] = "unhealthy"
                health_status["checks"]["read_write"] = "fail: value mismatch"
                
        except Exception as e:
            health_status["status"] = "unhealthy"
            health_status["checks"]["read_write"] = f"fail: {e}"
        
        # Check memory usage
        try:
            info = await self.redis.info("memory")
            used_memory = info.get("used_memory", 0)
            max_memory = info.get("maxmemory", 0)
            
            if max_memory > 0:
                memory_usage_ratio = used_memory / max_memory
                if memory_usage_ratio > 0.9:
                    health_status["checks"]["memory"] = f"warning: high usage ({memory_usage_ratio:.1%})"
                else:
                    health_status["checks"]["memory"] = "pass"
            else:
                health_status["checks"]["memory"] = "pass"
                
        except Exception as e:
            health_status["checks"]["memory"] = f"warning: {e}"
        
        return health_status


# ==========================================
# SPECIALIZED CACHE CLASSES
# ==========================================

class MovieCache(CacheManager):
    """Specialized cache for movie data"""
    
    def __init__(self, redis_client: Redis):
        super().__init__(redis_client, namespace="imdb_scraper:movies")
        self.movie_ttl = settings.CACHE_LONG_TTL  # 24 hours for movie data
        self.search_ttl = settings.CACHE_DEFAULT_TTL  # 1 hour for search results
    
    async def cache_movie(self, imdb_id: str, movie_data: Dict[str, Any]) -> bool:
        """Cache complete movie data"""
        return await self.set(f"movie:{imdb_id}", movie_data, ttl=self.movie_ttl)
    
    async def get_movie(self, imdb_id: str) -> Optional[Dict[str, Any]]:
        """Get cached movie data"""
        return await self.get(f"movie:{imdb_id}")
    
    async def cache_search_results(
        self, 
        search_params: Dict[str, Any], 
        results: List[Dict[str, Any]]
    ) -> bool:
        """Cache search results"""
        search_key = self._make_search_key(search_params)
        return await self.set(f"search:{search_key}", results, ttl=self.search_ttl)
    
    async def get_search_results(
        self, 
        search_params: Dict[str, Any]
    ) -> Optional[List[Dict[str, Any]]]:
        """Get cached search results"""
        search_key = self._make_search_key(search_params)
        return await self.get(f"search:{search_key}")
    
    def _make_search_key(self, search_params: Dict[str, Any]) -> str:
        """Generate search cache key from parameters"""
        import hashlib
        params_str = json.dumps(search_params, sort_keys=True)
        return hashlib.md5(params_str.encode()).hexdigest()
    
    async def invalidate_movie(self, imdb_id: str) -> bool:
        """Invalidate cached movie data"""
        return await self.delete(f"movie:{imdb_id}")
    
    async def clear_search_cache(self) -> int:
        """Clear all search results cache"""
        return await self.delete_pattern("search:*")


class SessionCache(CacheManager):
    """Specialized cache for user sessions and temporary data"""
    
    def __init__(self, redis_client: Redis):
        super().__init__(redis_client, namespace="imdb_scraper:sessions")
        self.session_ttl = 3600  # 1 hour for sessions
        self.temp_ttl = 300      # 5 minutes for temporary data
    
    async def create_session(self, session_id: str, session_data: Dict[str, Any]) -> bool:
        """Create user session"""
        return await self.set(f"session:{session_id}", session_data, ttl=self.session_ttl)
    
    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session data"""
        return await self.get(f"session:{session_id}")
    
    async def update_session(self, session_id: str, session_data: Dict[str, Any]) -> bool:
        """Update session data and refresh TTL"""
        return await self.set(f"session:{session_id}", session_data, ttl=self.session_ttl)
    
    async def delete_session(self, session_id: str) -> bool:
        """Delete session"""
        return await self.delete(f"session:{session_id}")
    
    async def store_temp_data(self, key: str, data: Any) -> bool:
        """Store temporary data with short TTL"""
        return await self.set(f"temp:{key}", data, ttl=self.temp_ttl)
    
    async def get_temp_data(self, key: str) -> Optional[Any]:
        """Get temporary data"""
        return await self.get(f"temp:{key}")


class ScrapingCache(CacheManager):
    """Specialized cache for scraping operations"""
    
    def __init__(self, redis_client: Redis):
        super().__init__(redis_client, namespace="imdb_scraper:scraping")
        self.job_ttl = 86400     # 24 hours for job status
        self.proxy_ttl = 3600    # 1 hour for proxy validation
        self.rate_limit_ttl = 60 # 1 minute for rate limiting
    
    async def cache_job_status(self, job_id: str, status_data: Dict[str, Any]) -> bool:
        """Cache scraping job status"""
        return await self.set(f"job:{job_id}", status_data, ttl=self.job_ttl)
    
    async def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job status"""
        return await self.get(f"job:{job_id}")
    
    async def cache_proxy_validation(self, proxy_host: str, validation_data: Dict[str, Any]) -> bool:
        """Cache proxy validation results"""
        return await self.set(f"proxy:{proxy_host}", validation_data, ttl=self.proxy_ttl)
    
    async def get_proxy_validation(self, proxy_host: str) -> Optional[Dict[str, Any]]:
        """Get cached proxy validation"""
        return await self.get(f"proxy:{proxy_host}")
    
    async def check_rate_limit(self, identifier: str, limit: int, window: int) -> Dict[str, Any]:
        """Check and update rate limit using sliding window"""
        current_time = int(asyncio.get_event_loop().time())
        key = f"rate_limit:{identifier}"
        
        try:
            # Use Redis pipeline for atomic operations
            async with self.redis.pipeline() as pipe:
                pipe.zremrangebyscore(key, 0, current_time - window)
                pipe.zcard(key)
                pipe.zadd(key, {str(current_time): current_time})
                pipe.expire(key, window)
                
                results = await pipe.execute()
                current_count = results[1]
                
                return {
                    "allowed": current_count < limit,
                    "current_count": current_count,
                    "limit": limit,
                    "window": window,
                    "reset_time": current_time + window
                }
                
        except Exception as e:
            logger.error(f"Rate limit check failed for {identifier}: {e}")
            return {
                "allowed": True,  # Allow on error
                "current_count": 0,
                "limit": limit,
                "window": window,
                "error": str(e)
            }


# ==========================================
# CACHE MANAGER FACTORY
# ==========================================

class CacheManagerFactory:
    """Factory for creating specialized cache managers"""
    
    def __init__(self, redis_client: Redis):
        self.redis_client = redis_client
        self._managers = {}
    
    def get_general_cache(self) -> CacheManager:
        """Get general purpose cache manager"""
        if "general" not in self._managers:
            self._managers["general"] = CacheManager(self.redis_client)
        return self._managers["general"]
    
    def get_movie_cache(self) -> MovieCache:
        """Get movie-specific cache manager"""
        if "movie" not in self._managers:
            self._managers["movie"] = MovieCache(self.redis_client)
        return self._managers["movie"]
    
    def get_session_cache(self) -> SessionCache:
        """Get session cache manager"""
        if "session" not in self._managers:
            self._managers["session"] = SessionCache(self.redis_client)
        return self._managers["session"]
    
    def get_scraping_cache(self) -> ScrapingCache:
        """Get scraping cache manager"""
        if "scraping" not in self._managers:
            self._managers["scraping"] = ScrapingCache(self.redis_client)
        return self._managers["scraping"]


# ==========================================
# GLOBAL INSTANCES
# ==========================================

# Global cache manager factory
cache_factory: Optional[CacheManagerFactory] = None

# Global cache manager instance (general purpose)
cache_manager: Optional[CacheManager] = None

# Specialized cache managers
movie_cache: Optional[MovieCache] = None
session_cache: Optional[SessionCache] = None
scraping_cache: Optional[ScrapingCache] = None


def get_cache_factory() -> CacheManagerFactory:
    """Get cache manager factory"""
    if cache_factory is None:
        raise RuntimeError("Cache not initialized. Call init_cache() first.")
    return cache_factory


def get_cache_manager() -> CacheManager:
    """Get general cache manager"""
    if cache_manager is None:
        raise RuntimeError("Cache not initialized. Call init_cache() first.")
    return cache_manager


async def init_cache() -> None:
    """Initialize all cache managers"""
    global cache_factory, cache_manager, movie_cache, session_cache, scraping_cache
    
    # Initialize Redis
    await init_redis()
    
    if redis_client is None:
        raise RuntimeError("Redis client not initialized")
    
    # Create cache factory and managers
    cache_factory = CacheManagerFactory(redis_client)
    cache_manager = cache_factory.get_general_cache()
    movie_cache = cache_factory.get_movie_cache()
    session_cache = cache_factory.get_session_cache()
    scraping_cache = cache_factory.get_scraping_cache()
    
    logger.info("Cache managers initialized successfully")


async def close_cache() -> None:
    """Close all cache connections"""
    await close_redis()
    
    global cache_factory, cache_manager, movie_cache, session_cache, scraping_cache
    cache_factory = None
    cache_manager = None
    movie_cache = None
    session_cache = None
    scraping_cache = None
    
    logger.info("Cache managers closed")


# ==========================================
# UTILITIES AND HELPERS
# ==========================================

async def warm_cache() -> None:
    """Warm up cache with frequently accessed data"""
    logger.info("Warming up cache...")
    
    try:
        # Pre-load common configuration
        if cache_manager:
            await cache_manager.set("app_version", settings.APP_VERSION, ttl=86400)
            await cache_manager.set("cache_warmed", True, ttl=3600)
        
        logger.info("Cache warmed successfully")
        
    except Exception as e:
        logger.error(f"Failed to warm cache: {e}")


async def cache_health_check() -> Dict[str, Any]:
    """Comprehensive cache health check"""
    if not cache_manager:
        return {"status": "unhealthy", "error": "Cache not initialized"}
    
    return await cache_manager.health_check()


# ==========================================
# EXPORTS
# ==========================================

__all__ = [
    # Redis client
    "redis_client",
    "init_redis",
    "close_redis",
    "test_redis_connection",
    
    # Cache managers
    "CacheManager",
    "MovieCache", 
    "SessionCache",
    "ScrapingCache",
    "CacheManagerFactory",
    
    # Global instances
    "cache_manager",
    "movie_cache",
    "session_cache", 
    "scraping_cache",
    "cache_factory",
    
    # Initialization
    "init_cache",
    "close_cache",
    "get_cache_manager",
    "get_cache_factory",
    
    # Utilities
    "warm_cache",
    "cache_health_check",
    
    # Helper classes
    "CacheSerializer",
    "CacheKeyManager",
]