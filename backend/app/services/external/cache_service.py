"""
Cache Service - High-level caching operations
"""

from typing import Any, Optional, Dict, List
from datetime import datetime, timedelta
import json

from app.core.cache import get_cache_manager, movie_cache, scraping_cache
from app.core.logging import get_logger

logger = get_logger(__name__)

class CacheService:
    """High-level cache management service"""
    
    def __init__(self):
        self.cache = get_cache_manager()
        self.movie_cache = movie_cache
        self.scraping_cache = scraping_cache
    
    async def cache_movie_data(self, movie_id: str, movie_data: Dict[str, Any], ttl: int = 3600) -> bool:
        """Cache complete movie data"""
        
        if not self.movie_cache:
            return False
        
        try:
            success = await self.movie_cache.cache_movie(movie_id, movie_data)
            if success:
                logger.debug(f"Cached movie data for {movie_id}")
            return success
        except Exception as e:
            logger.error(f"Failed to cache movie data: {e}")
            return False
    
    async def get_cached_movie(self, movie_id: str) -> Optional[Dict[str, Any]]:
        """Get cached movie data"""
        
        if not self.movie_cache:
            return None
        
        try:
            return await self.movie_cache.get_movie(movie_id)
        except Exception as e:
            logger.error(f"Failed to get cached movie: {e}")
            return None
    
    async def cache_search_results(
        self, 
        search_params: Dict[str, Any], 
        results: List[Dict[str, Any]],
        ttl: int = 1800
    ) -> bool:
        """Cache search results"""
        
        if not self.movie_cache:
            return False
        
        try:
            success = await self.movie_cache.cache_search_results(search_params, results)
            if success:
                logger.debug(f"Cached search results")
            return success
        except Exception as e:
            logger.error(f"Failed to cache search results: {e}")
            return False
    
    async def get_cached_search_results(
        self, 
        search_params: Dict[str, Any]
    ) -> Optional[List[Dict[str, Any]]]:
        """Get cached search results"""
        
        if not self.movie_cache:
            return None
        
        try:
            return await self.movie_cache.get_search_results(search_params)
        except Exception as e:
            logger.error(f"Failed to get cached search results: {e}")
            return None
    
    async def cache_scraping_job(self, job_id: str, job_data: Dict[str, Any]) -> bool:
        """Cache scraping job status"""
        
        if not self.scraping_cache:
            return False
        
        try:
            success = await self.scraping_cache.cache_job_status(job_id, job_data)
            if success:
                logger.debug(f"Cached scraping job {job_id}")
            return success
        except Exception as e:
            logger.error(f"Failed to cache scraping job: {e}")
            return False
    
    async def get_scraping_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get scraping job status from cache"""
        
        if not self.scraping_cache:
            return None
        
        try:
            return await self.scraping_cache.get_job_status(job_id)
        except Exception as e:
            logger.error(f"Failed to get scraping job status: {e}")
            return None
    
    async def cache_api_response(
        self, 
        endpoint: str, 
        params: Dict[str, Any], 
        response_data: Any,
        ttl: int = 300
    ) -> bool:
        """Cache API response"""
        
        if not self.cache:
            return False
        
        cache_key = f"api:{endpoint}:{hash(str(params))}"
        
        try:
            success = await self.cache.set(cache_key, response_data, ttl=ttl)
            if success:
                logger.debug(f"Cached API response for {endpoint}")
            return success
        except Exception as e:
            logger.error(f"Failed to cache API response: {e}")
            return False
    
    async def get_cached_api_response(
        self, 
        endpoint: str, 
        params: Dict[str, Any]
    ) -> Optional[Any]:
        """Get cached API response"""
        
        if not self.cache:
            return None
        
        cache_key = f"api:{endpoint}:{hash(str(params))}"
        
        try:
            return await self.cache.get(cache_key)
        except Exception as e:
            logger.error(f"Failed to get cached API response: {e}")
            return None
    
    async def cache_user_session(
        self, 
        session_id: str, 
        session_data: Dict[str, Any],
        ttl: int = 3600
    ) -> bool:
        """Cache user session data"""
        
        if not self.cache:
            return False
        
        cache_key = f"session:{session_id}"
        
        try:
            success = await self.cache.set(cache_key, session_data, ttl=ttl)
            if success:
                logger.debug(f"Cached user session {session_id}")
            return success
        except Exception as e:
            logger.error(f"Failed to cache user session: {e}")
            return False
    
    async def get_user_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get user session data from cache"""
        
        if not self.cache:
            return None
        
        cache_key = f"session:{session_id}"
        
        try:
            return await self.cache.get(cache_key)
        except Exception as e:
            logger.error(f"Failed to get user session: {e}")
            return None
    
    async def invalidate_user_session(self, session_id: str) -> bool:
        """Invalidate user session"""
        
        if not self.cache:
            return False
        
        cache_key = f"session:{session_id}"
        
        try:
            success = await self.cache.delete(cache_key)
            if success:
                logger.info(f"Invalidated user session {session_id}")
            return success
        except Exception as e:
            logger.error(f"Failed to invalidate user session: {e}")
            return False
    
    async def cache_rate_limit_info(
        self, 
        identifier: str, 
        limit_info: Dict[str, Any],
        ttl: int = 60
    ) -> bool:
        """Cache rate limit information"""
        
        if not self.cache:
            return False
        
        cache_key = f"rate_limit:{identifier}"
        
        try:
            success = await self.cache.set(cache_key, limit_info, ttl=ttl)
            return success
        except Exception as e:
            logger.error(f"Failed to cache rate limit info: {e}")
            return False
    
    async def get_rate_limit_info(self, identifier: str) -> Optional[Dict[str, Any]]:
        """Get rate limit information from cache"""
        
        if not self.cache:
            return None
        
        cache_key = f"rate_limit:{identifier}"
        
        try:
            return await self.cache.get(cache_key)
        except Exception as e:
            logger.error(f"Failed to get rate limit info: {e}")
            return None
    
    async def cache_application_config(
        self, 
        config_key: str, 
        config_data: Any,
        ttl: int = 86400
    ) -> bool:
        """Cache application configuration"""
        
        if not self.cache:
            return False
        
        cache_key = f"config:{config_key}"
        
        try:
            success = await self.cache.set(cache_key, config_data, ttl=ttl)
            if success:
                logger.debug(f"Cached application config {config_key}")
            return success
        except Exception as e:
            logger.error(f"Failed to cache application config: {e}")
            return False
    
    async def get_application_config(self, config_key: str) -> Optional[Any]:
        """Get application configuration from cache"""
        
        if not self.cache:
            return None
        
        cache_key = f"config:{config_key}"
        
        try:
            return await self.cache.get(cache_key)
        except Exception as e:
            logger.error(f"Failed to get application config: {e}")
            return None
    
    async def clear_all_caches(self) -> Dict[str, bool]:
        """Clear all application caches"""
        
        results = {}
        
        # Clear general cache
        if self.cache:
            try:
                await self.cache.clear_namespace()
                results["general"] = True
                logger.info("Cleared general cache")
            except Exception as e:
                logger.error(f"Failed to clear general cache: {e}")
                results["general"] = False
        
        # Clear movie cache
        if self.movie_cache:
            try:
                await self.movie_cache.clear_search_cache()
                results["movies"] = True
                logger.info("Cleared movie cache")
            except Exception as e:
                logger.error(f"Failed to clear movie cache: {e}")
                results["movies"] = False
        
        return results
    
    async def get_cache_statistics(self) -> Dict[str, Any]:
        """Get cache usage statistics"""
        
        stats = {
            "general_cache": {"available": False},
            "movie_cache": {"available": False},
            "scraping_cache": {"available": False}
        }
        
        # General cache stats
        if self.cache:
            try:
                cache_stats = await self.cache.get_stats()
                stats["general_cache"] = {
                    "available": True,
                    "stats": cache_stats
                }
            except Exception as e:
                logger.error(f"Failed to get general cache stats: {e}")
        
        # Movie cache stats
        if self.movie_cache:
            try:
                movie_stats = await self.movie_cache.get_stats()
                stats["movie_cache"] = {
                    "available": True,
                    "stats": movie_stats
                }
            except Exception as e:
                logger.error(f"Failed to get movie cache stats: {e}")
        
        # Scraping cache stats  
        if self.scraping_cache:
            try:
                scraping_stats = await self.scraping_cache.get_stats()
                stats["scraping_cache"] = {
                    "available": True,
                    "stats": scraping_stats
                }
            except Exception as e:
                logger.error(f"Failed to get scraping cache stats: {e}")
        
        return stats
    
    async def warm_up_cache(self) -> bool:
        """Warm up cache with frequently accessed data"""
        
        if not self.cache:
            return False
        
        try:
            # Cache application startup time
            await self.cache.set(
                "app:startup_time", 
                datetime.utcnow().isoformat(),
                ttl=86400
            )
            
            # Cache common configuration
            await self.cache.set(
                "app:cache_warmed",
                True,
                ttl=3600
            )
            
            logger.info("Cache warmed up successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to warm up cache: {e}")
            return False
    
    async def cache_health_check(self) -> Dict[str, Any]:
        """Perform cache health check"""
        
        health_status = {
            "status": "healthy",
            "services": {},
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Check general cache
        if self.cache:
            try:
                cache_health = await self.cache.health_check()
                health_status["services"]["general_cache"] = cache_health
            except Exception as e:
                health_status["services"]["general_cache"] = {
                    "status": "unhealthy",
                    "error": str(e)
                }
                health_status["status"] = "degraded"
        
        # Check movie cache
        if self.movie_cache:
            try:
                movie_health = await self.movie_cache.health_check()
                health_status["services"]["movie_cache"] = movie_health
            except Exception as e:
                health_status["services"]["movie_cache"] = {
                    "status": "unhealthy", 
                    "error": str(e)
                }
                health_status["status"] = "degraded"
        
        return health_status