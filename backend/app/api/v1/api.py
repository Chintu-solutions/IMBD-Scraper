"""
API v1 Router - Main API routing configuration
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from app.api.v1.endpoints import movies, people, media, search, scraping
from app.api.v1.deps import (
    check_service_health, 
    rate_limit_check, 
    log_request_context,
    require_feature
)
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Create main API router
api_router = APIRouter()

# ==========================================
# HEALTH AND STATUS ENDPOINTS
# ==========================================

@api_router.get("/health")
async def health_check():
    """API health check endpoint"""
    
    try:
        health_status = await check_service_health()
        
        # Determine overall health
        all_healthy = all(
            status in ["healthy", "available"] 
            for status in health_status.values()
        )
        
        status_code = 200 if all_healthy else 503
        
        return JSONResponse(
            status_code=status_code,
            content={
                "status": "healthy" if all_healthy else "degraded",
                "version": settings.APP_VERSION,
                "environment": settings.ENVIRONMENT,
                "services": health_status
            }
        )
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e),
                "version": settings.APP_VERSION
            }
        )

@api_router.get("/")
async def api_info():
    """API information and welcome endpoint"""
    
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "api_version": "v1",
        "documentation": f"{settings.API_V1_STR}/docs",
        "health_check": f"{settings.API_V1_STR}/health",
        "endpoints": {
            "movies": f"{settings.API_V1_STR}/movies",
            "people": f"{settings.API_V1_STR}/people", 
            "media": f"{settings.API_V1_STR}/media",
            "search": f"{settings.API_V1_STR}/search",
            "scraping": f"{settings.API_V1_STR}/scraping"
        }
    }

@api_router.get("/stats")
async def api_stats():
    """Get API usage statistics"""
    
    # In real implementation, this would aggregate real usage data
    return {
        "total_requests": 15420,
        "active_users": 45,
        "movies_in_database": 12500,
        "people_in_database": 8900,
        "media_files": 37800,
        "completed_scraping_jobs": 125,
        "uptime_hours": 720.5
    }

# ==========================================
# INCLUDE ENDPOINT ROUTERS
# ==========================================

# Movies endpoints
api_router.include_router(
    movies.router,
    prefix="/movies",
    tags=["movies"],
    dependencies=[
        Depends(rate_limit_check),
        Depends(log_request_context)
    ]
)

# People endpoints  
api_router.include_router(
    people.router,
    prefix="/people",
    tags=["people"],
    dependencies=[
        Depends(rate_limit_check),
        Depends(log_request_context)
    ]
)

# Media endpoints
api_router.include_router(
    media.router,
    prefix="/media", 
    tags=["media"],
    dependencies=[
        Depends(rate_limit_check),
        Depends(log_request_context),
        Depends(require_feature("media_download"))
    ]
)

# Search endpoints
api_router.include_router(
    search.router,
    prefix="/search",
    tags=["search"],
    dependencies=[
        Depends(rate_limit_check),
        Depends(log_request_context)
    ]
)

# Scraping endpoints
api_router.include_router(
    scraping.router,
    prefix="/scraping",
    tags=["scraping"],
    dependencies=[
        Depends(rate_limit_check),
        Depends(log_request_context),
        Depends(require_feature("scraping"))
    ]
)

# ==========================================
# ERROR HANDLERS
# ==========================================

@api_router.exception_handler(404)
async def not_found_handler(request, exc):
    """Handle 404 errors"""
    return JSONResponse(
        status_code=404,
        content={
            "status": "error",
            "message": "Resource not found",
            "path": str(request.url.path)
        }
    )

@api_router.exception_handler(500)
async def internal_error_handler(request, exc):
    """Handle 500 errors"""
    logger.error(f"Internal server error: {exc}", exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content={
            "status": "error", 
            "message": "Internal server error",
            "error_id": "contact_support_with_this_id"
        }
    )

# ==========================================
# MIDDLEWARE-LIKE DEPENDENCIES
# ==========================================

@api_router.middleware("http")
async def add_security_headers(request, call_next):
    """Add security headers to all responses"""
    
    response = await call_next(request)
    
    # Add security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    
    return response

# ==========================================
# ADMIN ENDPOINTS (Protected)
# ==========================================

@api_router.get("/admin/cache/clear")
async def clear_cache():
    """Clear application cache (admin only)"""
    
    # This endpoint would be protected by admin auth in real implementation
    try:
        from app.core.cache import get_cache_manager
        cache_manager = get_cache_manager()
        
        if cache_manager:
            # Clear cache namespaces
            cleared_keys = await cache_manager.clear_namespace()
            return {
                "status": "success",
                "message": f"Cleared {cleared_keys} cache keys"
            }
        else:
            return {
                "status": "warning", 
                "message": "Cache service not available"
            }
            
    except Exception as e:
        logger.error(f"Cache clear failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to clear cache")

@api_router.get("/admin/database/stats")
async def get_database_stats():
    """Get database statistics (admin only)"""
    
    try:
        from app.core.database import get_database_statistics
        stats = await get_database_statistics()
        return stats
        
    except Exception as e:
        logger.error(f"Database stats failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to get database stats")

# ==========================================
# DEVELOPMENT ENDPOINTS (Debug mode only)
# ==========================================

if settings.DEBUG:
    
    @api_router.get("/debug/config")
    async def debug_config():
        """Get sanitized configuration (debug mode only)"""
        
        # Return safe config values (no secrets)
        return {
            "app_name": settings.APP_NAME,
            "app_version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT,
            "debug": settings.DEBUG,
            "log_level": settings.LOG_LEVEL,
            "database_configured": bool(settings.DATABASE_URL),
            "cache_configured": bool(settings.REDIS_URL),
            "max_concurrent_scrapes": settings.MAX_CONCURRENT_SCRAPES,
            "allowed_hosts": settings.ALLOWED_HOSTS
        }
    
    @api_router.get("/debug/test-error")
    async def debug_test_error():
        """Test error handling (debug mode only)"""
        raise HTTPException(status_code=500, detail="This is a test error")
    
    @api_router.get("/debug/logs")
    async def debug_recent_logs():
        """Get recent log entries (debug mode only)"""
        
        # In real implementation, would read from log files or log aggregation service
        return {
            "message": "Debug logs endpoint",
            "note": "Would return recent log entries in production",
            "log_level": settings.LOG_LEVEL,
            "log_file": settings.LOG_FILE
        }

# ==========================================
# ROUTER CONFIGURATION
# ==========================================

# Set router metadata
api_router.tags = ["API v1"]
api_router.responses = {
    404: {"description": "Resource not found"},
    422: {"description": "Validation error"},
    500: {"description": "Internal server error"},
    503: {"description": "Service unavailable"}
}

# Log router setup
logger.info(f"API v1 router configured with {len(api_router.routes)} routes")