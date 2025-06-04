"""
Movie Service - Business logic for movie operations
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import selectinload

from app.models import Movie, Person, MediaFile, MovieCreate, MovieUpdate
from app.core.logging import get_logger
from app.core.cache import movie_cache

logger = get_logger(__name__)

class MovieService:
    """Service for movie business logic"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_movie_by_id(self, movie_id: int) -> Optional[Movie]:
        """Get movie by ID with caching"""
        
        # Try cache first
        if movie_cache:
            cached_movie = await movie_cache.get_movie(f"id:{movie_id}")
            if cached_movie:
                logger.debug(f"Movie {movie_id} retrieved from cache")
                return Movie(**cached_movie)
        
        # Get from database
        result = await self.db.execute(
            select(Movie)
            .options(selectinload(Movie.media_files))
            .where(Movie.id == movie_id)
        )
        movie = result.scalar_one_or_none()
        
        # Cache if found
        if movie and movie_cache:
            movie_data = {
                "id": movie.id,
                "imdb_id": movie.imdb_id,
                "title": movie.title,
                "year": movie.year,
                "imdb_rating": movie.imdb_rating,
                "genres": movie.genres,
                "plot_summary": movie.plot_summary
            }
            await movie_cache.cache_movie(f"id:{movie_id}", movie_data)
        
        return movie
    
    async def get_movie_by_imdb_id(self, imdb_id: str) -> Optional[Movie]:
        """Get movie by IMDb ID with caching"""
        
        # Try cache first
        if movie_cache:
            cached_movie = await movie_cache.get_movie(imdb_id)
            if cached_movie:
                logger.debug(f"Movie {imdb_id} retrieved from cache")
                return Movie(**cached_movie)
        
        # Get from database
        result = await self.db.execute(
            select(Movie)
            .options(selectinload(Movie.media_files))
            .where(Movie.imdb_id == imdb_id)
        )
        movie = result.scalar_one_or_none()
        
        # Cache if found
        if movie and movie_cache:
            movie_data = {
                "id": movie.id,
                "imdb_id": movie.imdb_id,
                "title": movie.title,
                "year": movie.year,
                "imdb_rating": movie.imdb_rating,
                "genres": movie.genres,
                "plot_summary": movie.plot_summary
            }
            await movie_cache.cache_movie(imdb_id, movie_data)
        
        return movie
    
    async def create_movie(self, movie_data: MovieCreate) -> Movie:
        """Create new movie"""
        
        # Check if movie already exists
        existing = await self.get_movie_by_imdb_id(movie_data.imdb_id)
        if existing:
            raise ValueError(f"Movie with IMDb ID {movie_data.imdb_id} already exists")
        
        # Create movie
        movie = Movie(**movie_data.model_dump())
        self.db.add(movie)
        await self.db.commit()
        await self.db.refresh(movie)
        
        # Cache the new movie
        if movie_cache:
            movie_dict = {
                "id": movie.id,
                "imdb_id": movie.imdb_id,
                "title": movie.title,
                "year": movie.year,
                "imdb_rating": movie.imdb_rating,
                "genres": movie.genres,
                "plot_summary": movie.plot_summary
            }
            await movie_cache.cache_movie(movie.imdb_id, movie_dict)
        
        logger.info(f"Created movie: {movie.title} ({movie.imdb_id})")
        return movie
    
    async def update_movie(self, movie_id: int, movie_data: MovieUpdate) -> Optional[Movie]:
        """Update movie"""
        
        movie = await self.get_movie_by_id(movie_id)
        if not movie:
            return None
        
        # Update fields
        update_data = movie_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(movie, field, value)
        
        await self.db.commit()
        await self.db.refresh(movie)
        
        # Invalidate cache
        if movie_cache:
            await movie_cache.invalidate_movie(movie.imdb_id)
            await movie_cache.invalidate_movie(f"id:{movie_id}")
        
        logger.info(f"Updated movie: {movie.title} ({movie.imdb_id})")
        return movie
    
    async def delete_movie(self, movie_id: int) -> bool:
        """Delete movie"""
        
        movie = await self.get_movie_by_id(movie_id)
        if not movie:
            return False
        
        await self.db.delete(movie)
        await self.db.commit()
        
        # Invalidate cache
        if movie_cache:
            await movie_cache.invalidate_movie(movie.imdb_id)
            await movie_cache.invalidate_movie(f"id:{movie_id}")
        
        logger.info(f"Deleted movie: {movie.title} ({movie.imdb_id})")
        return True
    
    async def get_movies_paginated(
        self, 
        page: int = 1, 
        size: int = 50,
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Get paginated movies with filters"""
        
        query = select(Movie)
        
        # Apply filters
        if filters:
            if filters.get("year"):
                query = query.where(Movie.year == filters["year"])
            
            if filters.get("genre"):
                query = query.where(Movie.genres.contains([filters["genre"]]))
            
            if filters.get("min_rating"):
                query = query.where(Movie.imdb_rating >= filters["min_rating"])
            
            if filters.get("max_rating"):
                query = query.where(Movie.imdb_rating <= filters["max_rating"])
            
            if filters.get("title"):
                query = query.where(
                    or_(
                        Movie.title.ilike(f"%{filters['title']}%"),
                        Movie.original_title.ilike(f"%{filters['title']}%")
                    )
                )
        
        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()
        
        # Get paginated results
        offset = (page - 1) * size
        query = query.offset(offset).limit(size)
        query = query.order_by(Movie.year.desc(), Movie.imdb_rating.desc())
        
        result = await self.db.execute(query)
        movies = result.scalars().all()
        
        return {
            "items": movies,
            "total": total,
            "page": page,
            "size": size,
            "has_next": offset + size < total,
            "has_prev": page > 1
        }
    
    async def get_top_rated_movies(self, limit: int = 10, min_votes: int = 1000) -> List[Movie]:
        """Get top rated movies"""
        
        query = select(Movie).where(
            and_(
                Movie.imdb_rating.is_not(None),
                Movie.imdb_votes >= min_votes
            )
        ).order_by(Movie.imdb_rating.desc()).limit(limit)
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def get_recent_movies(self, limit: int = 10) -> List[Movie]:
        """Get recently added movies"""
        
        query = select(Movie).order_by(Movie.created_at.desc()).limit(limit)
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def get_movies_by_year(self, year: int) -> List[Movie]:
        """Get all movies from a specific year"""
        
        query = select(Movie).where(Movie.year == year).order_by(Movie.imdb_rating.desc())
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def get_movies_by_genre(self, genre: str, limit: int = 50) -> List[Movie]:
        """Get movies by genre"""
        
        query = select(Movie).where(
            Movie.genres.contains([genre])
        ).order_by(Movie.imdb_rating.desc()).limit(limit)
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def get_similar_movies(self, movie_id: int, limit: int = 10) -> List[Movie]:
        """Get movies similar to the given movie"""
        
        # Get reference movie
        movie = await self.get_movie_by_id(movie_id)
        if not movie:
            return []
        
        # Find similar movies based on genres and year
        query = select(Movie).where(
            and_(
                Movie.id != movie_id,
                Movie.genres.overlap(movie.genres or [])
            )
        )
        
        # Prefer movies from similar time period
        if movie.year:
            query = query.order_by(
                func.abs(Movie.year - movie.year).asc(),
                Movie.imdb_rating.desc()
            )
        else:
            query = query.order_by(Movie.imdb_rating.desc())
        
        query = query.limit(limit)
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def get_movie_statistics(self) -> Dict[str, Any]:
        """Get movie statistics"""
        
        # Basic counts
        total_movies = await self.db.execute(select(func.count(Movie.id)))
        movies_with_rating = await self.db.execute(
            select(func.count(Movie.id)).where(Movie.imdb_rating.is_not(None))
        )
        
        # Average rating
        avg_rating = await self.db.execute(
            select(func.avg(Movie.imdb_rating)).where(Movie.imdb_rating.is_not(None))
        )
        
        # Year range
        year_stats = await self.db.execute(
            select(
                func.min(Movie.year).label('min_year'),
                func.max(Movie.year).label('max_year')
            ).where(Movie.year.is_not(None))
        )
        year_row = year_stats.fetchone()
        
        # Genre distribution (top 10)
        genre_stats = await self.db.execute(
            select(
                func.unnest(Movie.genres).label('genre'),
                func.count().label('count')
            ).where(Movie.genres.is_not(None))
            .group_by(func.unnest(Movie.genres))
            .order_by(func.count().desc())
            .limit(10)
        )
        
        return {
            "total_movies": total_movies.scalar() or 0,
            "movies_with_rating": movies_with_rating.scalar() or 0,
            "average_rating": round(float(avg_rating.scalar() or 0), 2),
            "year_range": {
                "min": year_row[0] if year_row else None,
                "max": year_row[1] if year_row else None
            },
            "top_genres": dict(genre_stats.fetchall())
        }
    
    async def update_movie_completion_status(self, movie_id: int, is_complete: bool) -> bool:
        """Update movie completion status"""
        
        movie = await self.get_movie_by_id(movie_id)
        if not movie:
            return False
        
        movie.is_complete = is_complete
        await self.db.commit()
        
        # Invalidate cache
        if movie_cache:
            await movie_cache.invalidate_movie(movie.imdb_id)
            await movie_cache.invalidate_movie(f"id:{movie_id}")
        
        return True
    
    async def bulk_update_movies(self, updates: List[Dict[str, Any]]) -> int:
        """Bulk update multiple movies"""
        
        updated_count = 0
        
        for update_data in updates:
            movie_id = update_data.get("id")
            if not movie_id:
                continue
            
            movie = await self.get_movie_by_id(movie_id)
            if not movie:
                continue
            
            # Update fields
            for field, value in update_data.items():
                if field != "id" and hasattr(movie, field):
                    setattr(movie, field, value)
            
            updated_count += 1
        
        await self.db.commit()
        
        # Clear movie cache after bulk update
        if movie_cache:
            await movie_cache.clear_search_cache()
        
        logger.info(f"Bulk updated {updated_count} movies")
        return updated_count