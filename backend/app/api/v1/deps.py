"""
API Dependencies
"""

from typing import Optional, Dict, Any
from fastapi import Depends, HTTPException, status, Header, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import verify_token, verify_api_key as verify_api_key_hash
from app.core.cache import get_cache_manager
from app.core.logging import get_logger

logger = get_logger(__name__)
security = HTTPBearer(auto_error=False)

# ==========================================
# DATABASE DEPENDENCIES
# ==========================================

async def get_db_session() -> AsyncSession:
    """Get database session dependency"""
    async for session in get_db():
        yield session

# ==========================================
# AUTHENTICATION DEPENDENCIES
# ==========================================

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[Dict[str, Any]]:
    """
    Get current user from JWT token.
    Returns None if no token provided (for optional auth).
    """
    if not credentials:
        return None
    
    token = credentials.credentials
    payload = verify_token(token)
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return {
        "user_id": payload.get("sub"),
        "permissions": payload.get("permissions", []),
        "token_type": payload.get("type", "access")
    }

async def require_auth(
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """Require authentication (user must be logged in)"""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return current_user

async def verify_api_key(
    api_key: Optional[str] = Header(None, alias="X-API-Key")
) -> Optional[str]:
    """
    Verify API key from header.
    Returns None if no API key provided (for optional auth).
    """
    if not api_key:
        return None
    
    # In a real implementation, you'd verify against stored hashed keys
    # For now, just validate format
    if not api_key.startswith("imdb_"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key format"
        )
    
    return api_key

async def require_api_key(
    api_key: str = Depends(verify_api_key)
) -> str:
    """Require API key authentication"""
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return api_key

# ==========================================
# PERMISSION DEPENDENCIES
# ==========================================

def require_permission(permission: str):
    """Create dependency that requires specific permission"""
    
    async def check_permission(
        current_user: Dict[str, Any] = Depends(require_auth)
    ) -> Dict[str, Any]:
        user_permissions = current_user.get("permissions", [])
        
        if permission not in user_permissions and "admin" not in user_permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission required: {permission}"
            )
        
        return current_user
    
    return check_permission

def require_admin():
    """Require admin permission"""
    return require_permission("admin")

# ==========================================
# RATE LIMITING DEPENDENCIES
# ==========================================

async def rate_limit_check(
    request_id: str = Header(None, alias="X-Request-ID"),
    user_ip: str = Header(None, alias="X-Forwarded-For")
) -> Dict[str, Any]:
    """Check rate limits for requests"""
    
    # Use user IP or request ID for rate limiting
    identifier = user_ip or request_id or "anonymous"
    
    cache_manager = get_cache_manager()
    if not cache_manager:
        # If cache is unavailable, allow request
        return {"allowed": True}
    
    # Check rate limit (100 requests per minute)
    # In real implementation, use Redis-based rate limiting
    return {"allowed": True, "identifier": identifier}

# ==========================================
# PAGINATION DEPENDENCIES
# ==========================================

async def get_pagination(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(50, ge=1, le=100, description="Page size")
) -> Dict[str, int]:
    """Get pagination parameters"""
    return {
        "page": page,
        "size": size,
        "offset": (page - 1) * size
    }

# ==========================================
# SEARCH DEPENDENCIES
# ==========================================

async def get_search_params(
    q: Optional[str] = Query(None, min_length=2, description="Search query"),
    sort_by: str = Query("created_at", description="Sort field"),
    sort_order: str = Query("desc", regex="^(asc|desc)$", description="Sort order")
) -> Dict[str, Any]:
    """Get common search parameters"""
    return {
        "query": q,
        "sort_by": sort_by,
        "sort_order": sort_order
    }

# ==========================================
# CACHE DEPENDENCIES
# ==========================================

async def get_cache_key_prefix(
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user)
) -> str:
    """Generate cache key prefix based on user"""
    if current_user:
        return f"user:{current_user['user_id']}"
    return "anonymous"

# ==========================================
# LOGGING DEPENDENCIES
# ==========================================

async def log_request_context(
    request_id: Optional[str] = Header(None, alias="X-Request-ID"),
    user_agent: Optional[str] = Header(None, alias="User-Agent"),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user)
) -> Dict[str, Any]:
    """Set up logging context for request"""
    
    context = {
        "request_id": request_id,
        "user_agent": user_agent,
    }
    
    if current_user:
        context["user_id"] = current_user["user_id"]
    
    return context

# ==========================================
# VALIDATION DEPENDENCIES
# ==========================================

async def validate_imdb_id(imdb_id: str) -> str:
    """Validate IMDb ID format"""
    import re
    
    if not re.match(r"^tt\d{7,8}$", imdb_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid IMDb ID format. Expected format: tt1234567"
        )
    
    return imdb_id

async def validate_person_imdb_id(imdb_id: str) -> str:
    """Validate person IMDb ID format"""
    import re
    
    if not re.match(r"^nm\d{7,8}$", imdb_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid person IMDb ID format. Expected format: nm1234567"
        )
    
    return imdb_id

# ==========================================
# FEATURE FLAGS DEPENDENCIES
# ==========================================

async def check_feature_enabled(feature_name: str) -> bool:
    """Check if a feature is enabled"""
    
    # In real implementation, this would check feature flags from config/database
    feature_flags = {
        "scraping": True,
        "media_download": True,
        "advanced_search": True,
        "recommendations": True,
        "analytics": False,  # Example disabled feature
    }
    
    return feature_flags.get(feature_name, False)

def require_feature(feature_name: str):
    """Create dependency that requires feature to be enabled"""
    
    async def check_feature():
        if not await check_feature_enabled(feature_name):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Feature '{feature_name}' is currently disabled"
            )
        return True
    
    return check_feature

# ==========================================
# HEALTH CHECK DEPENDENCIES
# ==========================================

async def check_service_health() -> Dict[str, Any]:
    """Check service health status"""
    
    health_status = {
        "database": "unknown",
        "cache": "unknown",
        "storage": "unknown"
    }
    
    # Check database
    try:
        async for db in get_db():
            # Simple health check query
            await db.execute("SELECT 1")
            health_status["database"] = "healthy"
            break
    except Exception:
        health_status["database"] = "unhealthy"
    
    # Check cache
    try:
        cache_manager = get_cache_manager()
        if cache_manager:
            await cache_manager.set("health_check", "ok", ttl=60)
            health_status["cache"] = "healthy"
        else:
            health_status["cache"] = "unavailable"
    except Exception:
        health_status["cache"] = "unhealthy"
    
    # Storage is assumed healthy for now
    health_status["storage"] = "healthy"
    
    return health_status

# ==========================================
# CLEANUP DEPENDENCIES
# ==========================================

async def cleanup_temp_data():
    """Cleanup temporary data after request"""
    # This would run after request completion
    # For now, just a placeholder
    pass