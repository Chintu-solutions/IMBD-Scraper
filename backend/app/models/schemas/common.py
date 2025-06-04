"""
Common Pydantic Schemas
"""

from datetime import datetime, date
from typing import Optional, List, Any, Generic, TypeVar
from pydantic import BaseModel, Field, ConfigDict

T = TypeVar('T')

class BaseResponse(BaseModel):
    """Base response model"""
    status: str = "success"
    message: Optional[str] = None

class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated response model"""
    items: List[T]
    total: int
    page: int = 1
    size: int = 50
    has_next: bool = False
    has_prev: bool = False

class FilterConfig(BaseModel):
    """Movie search filters"""
    title_types: Optional[List[str]] = ["movie"]
    year_start: Optional[int] = None
    year_end: Optional[int] = None
    rating_min: Optional[float] = None
    rating_max: Optional[float] = None
    genres: Optional[List[str]] = None
    exclude_genres: Optional[List[str]] = None
    certificates: Optional[List[str]] = None
    sort_by: str = "popularity"
    sort_order: str = "desc"
    include_adult: bool = False
    max_pages: int = 3

class ProxyConfig(BaseModel):
    """Proxy configuration"""
    host: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    ipstack_api_key: Optional[str] = None

class ScrapeJobConfig(BaseModel):
    """Scraping job configuration"""
    filters: FilterConfig
    proxy: Optional[ProxyConfig] = None
    download_media: bool = True
    max_concurrent: int = 3

class TimestampMixin(BaseModel):
    """Timestamp fields mixin"""
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)