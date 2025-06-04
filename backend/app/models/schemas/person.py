"""
Person Pydantic Schemas
"""

from datetime import date
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict

from .common import TimestampMixin

class PersonBase(BaseModel):
    """Base person fields"""
    imdb_id: str = Field(..., pattern=r"^nm\d{7,8}$")
    name: str = Field(..., min_length=1, max_length=200)
    birth_date: Optional[date] = None
    death_date: Optional[date] = None
    birth_place: Optional[str] = Field(None, max_length=200)

class PersonCreate(PersonBase):
    """Create person schema"""
    bio: Optional[str] = None
    height: Optional[str] = Field(None, max_length=20)
    known_for_titles: Optional[List[str]] = []
    primary_profession: Optional[List[str]] = []
    awards_summary: Optional[str] = None

class PersonUpdate(BaseModel):
    """Update person schema"""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    birth_date: Optional[date] = None
    death_date: Optional[date] = None
    birth_place: Optional[str] = Field(None, max_length=200)
    bio: Optional[str] = None
    height: Optional[str] = Field(None, max_length=20)

class Person(PersonBase, TimestampMixin):
    """Person response schema"""
    id: int
    bio: Optional[str] = None
    primary_profession: Optional[List[str]] = []
    is_complete: bool = False
    
    model_config = ConfigDict(from_attributes=True)

class PersonDetail(Person):
    """Detailed person response"""
    height: Optional[str] = None
    known_for_titles: Optional[List[str]] = []
    awards_summary: Optional[str] = None
    
    # Related data counts
    movies_count: Optional[int] = 0
    as_actor_count: Optional[int] = 0
    as_director_count: Optional[int] = 0
    as_writer_count: Optional[int] = 0

class PersonRole(BaseModel):
    """Person role in a movie"""
    person_id: int
    name: str
    role_type: str  # actor, director, writer, producer
    character_name: Optional[str] = None
    billing_order: Optional[int] = None
    job_title: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)