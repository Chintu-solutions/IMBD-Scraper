"""
Models Package - Main imports
"""

# Database models
from .database import Base, Movie, Person, MediaFile

# Pydantic schemas
from .schemas import (
    # Common
    BaseResponse, PaginatedResponse, FilterConfig, ProxyConfig, ScrapeJobConfig,
    
    # Movie schemas
    MovieBase, MovieCreate, MovieUpdate, Movie as MovieSchema, MovieDetail, MovieSearchResult,
    
    # Person schemas
    PersonBase, PersonCreate, PersonUpdate, Person as PersonSchema, PersonDetail, PersonRole,
    
    # Media schemas
    MediaFileBase, MediaFileCreate, MediaFileUpdate, MediaFile as MediaFileSchema, MediaFileDownload,
)

__all__ = [
    # Database models
    "Base", "Movie", "Person", "MediaFile",
    
    # Common schemas
    "BaseResponse", "PaginatedResponse", "FilterConfig", "ProxyConfig", "ScrapeJobConfig",
    
    # Movie schemas
    "MovieBase", "MovieCreate", "MovieUpdate", "MovieSchema", "MovieDetail", "MovieSearchResult",
    
    # Person schemas
    "PersonBase", "PersonCreate", "PersonUpdate", "PersonSchema", "PersonDetail", "PersonRole",
    
    # Media schemas
    "MediaFileBase", "MediaFileCreate", "MediaFileUpdate", "MediaFileSchema", "MediaFileDownload",
]