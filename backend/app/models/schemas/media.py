"""
Media File Pydantic Schemas
"""

from typing import Optional
from pydantic import BaseModel, Field, ConfigDict, HttpUrl

from .common import TimestampMixin

class MediaFileBase(BaseModel):
    """Base media file fields"""
    file_type: str = Field(..., pattern=r"^(poster|still|trailer|clip)$")
    original_url: str = Field(..., max_length=1000)
    category: Optional[str] = Field(None, max_length=50)
    description: Optional[str] = Field(None, max_length=500)

class MediaFileCreate(MediaFileBase):
    """Create media file schema"""
    movie_id: int
    width: Optional[int] = Field(None, ge=1)
    height: Optional[int] = Field(None, ge=1)
    duration: Optional[int] = Field(None, ge=0)  # seconds for videos
    format: Optional[str] = Field(None, max_length=10)
    quality: Optional[str] = Field(None, pattern=r"^(high|medium|low|original)$")

class MediaFileUpdate(BaseModel):
    """Update media file schema"""
    local_path: Optional[str] = Field(None, max_length=500)
    file_size: Optional[int] = Field(None, ge=0)
    is_downloaded: Optional[bool] = None
    download_failed: Optional[bool] = None
    failure_reason: Optional[str] = Field(None, max_length=200)
    width: Optional[int] = Field(None, ge=1)
    height: Optional[int] = Field(None, ge=1)
    duration: Optional[int] = Field(None, ge=0)

class MediaFile(MediaFileBase, TimestampMixin):
    """Media file response schema"""
    id: int
    movie_id: int
    local_path: Optional[str] = None
    file_size: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None
    duration: Optional[int] = None
    format: Optional[str] = None
    quality: Optional[str] = None
    is_downloaded: bool = False
    download_failed: bool = False
    failure_reason: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)

class MediaFileDownload(BaseModel):
    """Media file download request"""
    media_file_ids: list[int]
    quality_preference: str = Field("high", pattern=r"^(high|medium|low|original)$")
    overwrite_existing: bool = False