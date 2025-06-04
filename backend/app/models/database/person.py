"""
Person Database Model
"""

from sqlalchemy import Column, Integer, String, Text, Date, Boolean, Table, ForeignKey
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import relationship

from .base import Base, TimestampMixin

# Association table for movie-person relationship
movie_person = Table(
    'movie_person', Base.metadata,
    Column('movie_id', Integer, ForeignKey('movies.id'), primary_key=True),
    Column('person_id', Integer, ForeignKey('people.id'), primary_key=True),
    Column('role_type', String(20), nullable=False),  # actor, director, writer, producer
    Column('character_name', String(200)),  # For actors
    Column('billing_order', Integer),  # Order in credits
    Column('job_title', String(100))  # Specific job for crew
)

class Person(Base, TimestampMixin):
    __tablename__ = "people"
    
    id = Column(Integer, primary_key=True, index=True)
    imdb_id = Column(String(20), unique=True, nullable=False, index=True)
    
    # Basic Info
    name = Column(String(200), nullable=False, index=True)
    birth_date = Column(Date)
    death_date = Column(Date)
    birth_place = Column(String(200))
    
    # Biography
    bio = Column(Text)
    height = Column(String(20))  # e.g., "5' 10""
    
    # Career
    known_for_titles = Column(ARRAY(String))  # IMDb IDs of famous movies
    primary_profession = Column(ARRAY(String))  # actor, director, writer, etc.
    
    # Awards and Recognition
    awards_summary = Column(Text)
    
    # Scraping metadata
    last_scraped = Column(Date)
    is_complete = Column(Boolean, default=False)
    
    # Relationships
    movies = relationship("Movie", secondary=movie_person, back_populates="cast_crew")
    
    def __repr__(self):
        return f"<Person(imdb_id='{self.imdb_id}', name='{self.name}')>"