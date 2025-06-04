"""
Media File Database Model
"""

from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, BigInteger
from sqlalchemy.orm import relationship

from .base import Base, TimestampMixin

class MediaFile(Base, TimestampMixin):
    __tablename__ = "media_files"
    
    id = Column(Integer, primary_key=True, index=True)
    movie_id = Column(Integer, ForeignKey("movies.id"), nullable=False, index=True)
    
    # File Info
    file_type = Column(String(20), nullable=False, index=True)  # poster, still, trailer, clip
    original_url = Column(String(1000), nullable=False)
    local_path = Column(String(500))
    file_size = Column(BigInteger)  # bytes
    
    # Media Properties
    width = Column(Integer)
    height = Column(Integer)
    duration = Column(Integer)  # seconds for videos
    format = Column(String(10))  # jpg, png, mp4, webm
    quality = Column(String(20))  # high, medium, low, original
    
    # Status
    is_downloaded = Column(Boolean, default=False)
    download_failed = Column(Boolean, default=False)
    failure_reason = Column(String(200))
    
    # Categorization
    category = Column(String(50))  # production_still, behind_scenes, promotional
    description = Column(String(500))
    
    # Relationship
    movie = relationship("Movie", back_populates="media_files")
    
    def __repr__(self):
        return f"<MediaFile(movie_id={self.movie_id}, type='{self.file_type}', local_path='{self.local_path}')>"