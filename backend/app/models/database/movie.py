"""
Movie Database Model
"""

from sqlalchemy import Column, Integer, String, Float, Text, Date, Boolean, JSON
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import relationship

from .base import Base, TimestampMixin

class Movie(Base, TimestampMixin):
    __tablename__ = "movies"
    
    id = Column(Integer, primary_key=True, index=True)
    imdb_id = Column(String(20), unique=True, nullable=False, index=True)
    
    # Basic Info
    title = Column(String(500), nullable=False, index=True)
    original_title = Column(String(500))
    year = Column(Integer, index=True)
    release_date = Column(Date)
    runtime = Column(Integer)  # minutes
    
    # Ratings & Reviews
    imdb_rating = Column(Float)
    imdb_votes = Column(Integer)
    metascore = Column(Integer)
    
    # Content
    plot_summary = Column(Text)
    plot_outline = Column(Text)
    genres = Column(ARRAY(String))
    mpaa_rating = Column(String(10))  # G, PG, PG-13, R, NC-17
    
    # Technical
    aspect_ratio = Column(String(20))
    sound_mix = Column(ARRAY(String))
    color_info = Column(String(50))
    
    # Financial
    budget = Column(Integer)  # USD
    box_office_worldwide = Column(Integer)  # USD
    opening_weekend = Column(Integer)  # USD
    
    # Additional Data
    awards = Column(JSON)  # Store awards as JSON
    trivia = Column(ARRAY(Text))
    goofs = Column(ARRAY(Text))
    filming_locations = Column(ARRAY(String))
    
    # Scraping metadata
    last_scraped = Column(Date)
    scrape_version = Column(String(10), default="1.0")
    is_complete = Column(Boolean, default=False)
    
    # Relationships
    cast_crew = relationship("Person", secondary="movie_person", back_populates="movies")
    media_files = relationship("MediaFile", back_populates="movie", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Movie(imdb_id='{self.imdb_id}', title='{self.title}')>"