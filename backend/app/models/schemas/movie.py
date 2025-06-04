"""
Movie Pydantic Schemas
"""

from datetime import date
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

from .common import TimestampMixin

class MovieBase(BaseModel):
    """Base movie fields"""
    imdb_id: str = Field(..., pattern=r"^tt\d{7,8}$")
    title: str = Field(..., min_length=1, max_length=500)
    original_title: Optional[str] = Field(None, max_length=500)
    year: Optional[int] = Field(None, ge=1800, le=2030)
    release_date: Optional[date] = None
    runtime: Optional[int] = Field(None, ge=1, le=1000)

class MovieCreate(MovieBase):
    """Create movie schema"""
    # Ratings
    imdb_rating: Optional[float] = Field(None, ge=0.0, le=10.0)
    imdb_votes: Optional[int] = Field(None, ge=0)
    metascore: Optional[int] = Field(None, ge=0, le=100)
    
    # Content
    plot_summary: Optional[str] = None
    plot_outline: Optional[str] = None
    genres: Optional[List[str]] = []
    mpaa_rating: Optional[str] = None
    
    # Technical
    aspect_ratio: Optional[str] = None
    sound_mix: Optional[List[str]] = []
    color_info: Optional[str] = None
    
    # Financial
    budget: Optional[int] = Field(None, ge=0)
    box_office_worldwide: Optional[int] = Field(None, ge=0)
    opening_weekend: Optional[int] = Field(None, ge=0)
    
    # Additional
    awards: Optional[Dict[str, Any]] = {}
    trivia: Optional[List[str]] = []
    goofs: Optional[List[str]] = []
    filming_locations: Optional[List[str]] = []

class MovieUpdate(BaseModel):
    """Update movie schema"""
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    original_title: Optional[str] = Field(None, max_length=500)
    year: Optional[int] = Field(None, ge=1800, le=2030)
    release_date: Optional[date] = None
    runtime: Optional[int] = Field(None, ge=1, le=1000)
    imdb_rating: Optional[float] = Field(None, ge=0.0, le=10.0)
    plot_summary: Optional[str] = None
    genres: Optional[List[str]] = None
    mpaa_rating: Optional[str] = None

class Movie(MovieBase, TimestampMixin):
    """Movie response schema"""
    id: int
    imdb_rating: Optional[float] = None
    imdb_votes: Optional[int] = None
    metascore: Optional[int] = None
    plot_summary: Optional[str] = None
    genres: Optional[List[str]] = []
    mpaa_rating: Optional[str] = None
    is_complete: bool = False
    
    model_config = ConfigDict(from_attributes=True)

class MovieDetail(Movie):
    """Detailed movie response with relationships"""
    plot_outline: Optional[str] = None
    aspect_ratio: Optional[str] = None
    sound_mix: Optional[List[str]] = []
    color_info: Optional[str] = None
    budget: Optional[int] = None
    box_office_worldwide: Optional[int] = None
    opening_weekend: Optional[int] = None
    awards: Optional[Dict[str, Any]] = {}
    trivia: Optional[List[str]] = []
    goofs: Optional[List[str]] = []
    filming_locations: Optional[List[str]] = []
    
    # Related data counts
    cast_count: Optional[int] = 0
    crew_count: Optional[int] = 0
    images_count: Optional[int] = 0
    videos_count: Optional[int] = 0

class MovieSearchResult(BaseModel):
    """Movie search result schema"""
    id: int
    imdb_id: str
    title: str
    year: Optional[int] = None
    imdb_rating: Optional[float] = None
    genres: Optional[List[str]] = []
    poster_url: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)