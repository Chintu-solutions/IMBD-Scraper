"""
Search Service - Business logic for search operations
"""

from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, text
from sqlalchemy.orm import selectinload

from app.models import Movie, Person, MediaFile
from app.core.logging import get_logger
from app.core.cache import get_cache_manager

logger = get_logger(__name__)

class SearchService:
    """Service for search business logic"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.cache = get_cache_manager()
    
    async def search_movies(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 20
    ) -> List[Movie]:
        """Search movies with filters and caching"""
        
        # Generate cache key
        cache_key = f"search:movies:{hash(query + str(filters))}"
        
        # Try cache first
        if self.cache:
            cached_results = await self.cache.get(cache_key)
            if cached_results:
                logger.debug(f"Movie search results retrieved from cache")
                return [Movie(**movie) for movie in cached_results]
        
        # Build search query
        search_query = select(Movie).where(
            or_(
                Movie.title.ilike(f"%{query}%"),
                Movie.original_title.ilike(f"%{query}%")
            )
        )
        
        # Apply filters
        if filters:
            if filters.get("year"):
                search_query = search_query.where(Movie.year == filters["year"])
            
            if filters.get("genre"):
                search_query = search_query.where(Movie.genres.contains([filters["genre"]]))
            
            if filters.get("min_rating"):
                search_query = search_query.where(Movie.imdb_rating >= filters["min_rating"])
            
            if filters.get("max_rating"):
                search_query = search_query.where(Movie.imdb_rating <= filters["max_rating"])
        
        # Order by relevance (rating and year)
        search_query = search_query.order_by(
            Movie.imdb_rating.desc().nulls_last(),
            Movie.year.desc().nulls_last()
        ).limit(limit)
        
        result = await self.db.execute(search_query)
        movies = result.scalars().all()
        
        # Cache results
        if self.cache and movies:
            movie_data = [
                {
                    "id": movie.id,
                    "imdb_id": movie.imdb_id,
                    "title": movie.title,
                    "year": movie.year,
                    "imdb_rating": movie.imdb_rating,
                    "genres": movie.genres
                }
                for movie in movies
            ]
            await self.cache.set(cache_key, movie_data, ttl=1800)  # 30 minutes
        
        return movies
    
    async def search_people(
        self,
        query: str,
        profession: Optional[str] = None,
        limit: int = 20
    ) -> List[Person]:
        """Search people by name"""
        
        search_query = select(Person).where(
            Person.name.ilike(f"%{query}%")
        )
        
        if profession:
            search_query = search_query.where(
                Person.primary_profession.contains([profession])
            )
        
        search_query = search_query.order_by(Person.name).limit(limit)
        
        result = await self.db.execute(search_query)
        return result.scalars().all()
    
    async def advanced_movie_search(
        self,
        title: Optional[str] = None,
        year_start: Optional[int] = None,
        year_end: Optional[int] = None,
        rating_min: Optional[float] = None,
        rating_max: Optional[float] = None,
        genres: Optional[List[str]] = None,
        mpaa_rating: Optional[str] = None,
        min_votes: Optional[int] = None,
        runtime_min: Optional[int] = None,
        runtime_max: Optional[int] = None,
        sort_by: str = "rating",
        sort_order: str = "desc",
        limit: int = 50
    ) -> List[Movie]:
        """Advanced movie search with multiple filters"""
        
        query = select(Movie)
        
        # Apply filters
        if title:
            query = query.where(
                or_(
                    Movie.title.ilike(f"%{title}%"),
                    Movie.original_title.ilike(f"%{title}%")
                )
            )
        
        if year_start and year_end:
            query = query.where(
                and_(
                    Movie.year >= year_start,
                    Movie.year <= year_end
                )
            )
        elif year_start:
            query = query.where(Movie.year >= year_start)
        elif year_end:
            query = query.where(Movie.year <= year_end)
        
        if rating_min:
            query = query.where(Movie.imdb_rating >= rating_min)
        if rating_max:
            query = query.where(Movie.imdb_rating <= rating_max)
        
        if genres:
            for genre in genres:
                query = query.where(Movie.genres.contains([genre]))
        
        if mpaa_rating:
            query = query.where(Movie.mpaa_rating == mpaa_rating)
        
        if min_votes:
            query = query.where(Movie.imdb_votes >= min_votes)
        
        if runtime_min:
            query = query.where(Movie.runtime >= runtime_min)
        if runtime_max:
            query = query.where(Movie.runtime <= runtime_max)
        
        # Apply sorting
        if sort_by == "rating":
            order_field = Movie.imdb_rating
        elif sort_by == "year":
            order_field = Movie.year
        elif sort_by == "title":
            order_field = Movie.title
        elif sort_by == "votes":
            order_field = Movie.imdb_votes
        else:
            order_field = Movie.imdb_rating
        
        if sort_order == "desc":
            query = query.order_by(order_field.desc().nulls_last())
        else:
            query = query.order_by(order_field.asc().nulls_last())
        
        query = query.limit(limit)
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def get_search_suggestions(
        self,
        query: str,
        type: str = "movie",
        limit: int = 10
    ) -> List[str]:
        """Get search suggestions for autocomplete"""
        
        if type == "movie":
            search_query = select(Movie.title).where(
                Movie.title.ilike(f"{query}%")
            ).order_by(
                Movie.imdb_rating.desc().nulls_last()
            ).limit(limit)
            
            result = await self.db.execute(search_query)
            return [row[0] for row in result.fetchall()]
        
        else:  # person
            search_query = select(Person.name).where(
                Person.name.ilike(f"{query}%")
            ).order_by(Person.name).limit(limit)
            
            result = await self.db.execute(search_query)
            return [row[0] for row in result.fetchall()]
    
    async def get_similar_movies(self, movie_id: int, limit: int = 10) -> List[Movie]:
        """Get movies similar to the given movie"""
        
        # Get reference movie
        movie_result = await self.db.execute(select(Movie).where(Movie.id == movie_id))
        movie = movie_result.scalar_one_or_none()
        
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
                func.abs(Movie.year - movie.year).asc().nulls_last(),
                Movie.imdb_rating.desc().nulls_last()
            )
        else:
            query = query.order_by(Movie.imdb_rating.desc().nulls_last())
        
        query = query.limit(limit)
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def get_trending_movies(
        self,
        period: str = "week",
        limit: int = 20
    ) -> List[Movie]:
        """Get trending movies based on recent activity"""
        
        # For now, return recently added movies with high ratings
        # In a real system, this would be based on user activity, views, etc.
        
        if period == "day":
            days = 1
        elif period == "week":
            days = 7
        else:  # month
            days = 30
        
        query = select(Movie).where(
            and_(
                Movie.created_at >= func.now() - text(f"INTERVAL '{days} days'"),
                Movie.imdb_rating >= 6.0
            )
        ).order_by(
            Movie.imdb_rating.desc(),
            Movie.created_at.desc()
        ).limit(limit)
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def get_available_genres(self) -> List[str]:
        """Get all available genres from movies"""
        
        cache_key = "search:available_genres"
        
        # Try cache first
        if self.cache:
            cached_genres = await self.cache.get(cache_key)
            if cached_genres:
                return cached_genres
        
        # Get from database
        result = await self.db.execute(
            select(func.unnest(Movie.genres).label('genre'))
            .where(Movie.genres.is_not(None))
            .distinct()
        )
        
        genres = sorted([row[0] for row in result.fetchall()])
        
        # Cache results
        if self.cache:
            await self.cache.set(cache_key, genres, ttl=86400)  # 24 hours
        
        return genres
    
    async def get_available_years(self) -> Dict[str, Optional[int]]:
        """Get available year range from movies"""
        
        cache_key = "search:available_years"
        
        # Try cache first
        if self.cache:
            cached_years = await self.cache.get(cache_key)
            if cached_years:
                return cached_years
        
        # Get from database
        result = await self.db.execute(
            select(
                func.min(Movie.year).label('min_year'),
                func.max(Movie.year).label('max_year')
            ).where(Movie.year.is_not(None))
        )
        
        row = result.fetchone()
        years = {
            "min_year": row[0] if row else None,
            "max_year": row[1] if row else None
        }
        
        # Cache results
        if self.cache:
            await self.cache.set(cache_key, years, ttl=86400)  # 24 hours
        
        return years
    
    async def get_search_statistics(self) -> Dict[str, Any]:
        """Get search and database statistics"""
        
        # Movie stats
        movie_stats = await self.db.execute(
            select(
                func.count(Movie.id).label('total_movies'),
                func.count(Movie.imdb_rating).label('movies_with_rating'),
                func.avg(Movie.imdb_rating).label('avg_rating'),
                func.min(Movie.year).label('oldest_year'),
                func.max(Movie.year).label('newest_year')
            )
        )
        movie_row = movie_stats.fetchone()
        
        # Person stats
        person_stats = await self.db.execute(
            select(func.count(Person.id).label('total_people'))
        )
        person_row = person_stats.fetchone()
        
        # Media stats
        media_stats = await self.db.execute(
            select(func.count(MediaFile.id).label('total_media'))
        )
        media_row = media_stats.fetchone()
        
        # Genre distribution (top 10)
        genre_stats = await self.db.execute(
            select(
                func.unnest(Movie.genres).label('genre'),
                func.count().label('count')
            ).where(Movie.genres.is_not(None))
            .group_by(text('genre'))
            .order_by(text('count DESC'))
            .limit(10)
        )
        top_genres = dict(genre_stats.fetchall())
        
        return {
            "movies": {
                "total": movie_row[0] if movie_row else 0,
                "with_rating": movie_row[1] if movie_row else 0,
                "avg_rating": round(float(movie_row[2]), 2) if movie_row and movie_row[2] else 0,
                "year_range": {
                    "min": movie_row[3] if movie_row else None,
                    "max": movie_row[4] if movie_row else None
                }
            },
            "people": {
                "total": person_row[0] if person_row else 0
            },
            "media": {
                "total": media_row[0] if media_row else 0
            },
            "top_genres": top_genres
        }
    
    async def full_text_search(
        self,
        query: str,
        entity_type: str = "all",
        limit: int = 50
    ) -> Dict[str, List[Any]]:
        """Full-text search across movies and people"""
        
        results = {"movies": [], "people": []}
        
        if entity_type in ["all", "movies"]:
            # Search movies
            movie_query = select(Movie).where(
                or_(
                    Movie.title.ilike(f"%{query}%"),
                    Movie.original_title.ilike(f"%{query}%"),
                    Movie.plot_summary.ilike(f"%{query}%")
                )
            ).order_by(
                Movie.imdb_rating.desc().nulls_last()
            ).limit(limit)
            
            movie_result = await self.db.execute(movie_query)
            results["movies"] = movie_result.scalars().all()
        
        if entity_type in ["all", "people"]:
            # Search people
            person_query = select(Person).where(
                or_(
                    Person.name.ilike(f"%{query}%"),
                    Person.bio.ilike(f"%{query}%")
                )
            ).order_by(Person.name).limit(limit)
            
            person_result = await self.db.execute(person_query)
            results["people"] = person_result.scalars().all()
        
        return results
    
    async def search_by_cast_crew(
        self,
        person_name: str,
        role_type: Optional[str] = None
    ) -> List[Movie]:
        """Search movies by cast or crew member"""
        
        # This would require joining with the movie_person association table
        # For now, return empty list as placeholder
        # In real implementation, would use proper joins
        
        return []
    
    async def get_popular_searches(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get popular search terms (would require search tracking)"""
        
        # This would require tracking search queries in the database
        # For now, return mock data
        
        return [
            {"query": "avengers", "count": 1250},
            {"query": "batman", "count": 980},
            {"query": "marvel", "count": 875},
            {"query": "star wars", "count": 720},
            {"query": "spider-man", "count": 680}
        ]
    
    async def clear_search_cache(self) -> bool:
        """Clear all search-related cache"""
        
        if not self.cache:
            return False
        
        # Clear search cache patterns
        await self.cache.delete_pattern("search:*")
        
        logger.info("Search cache cleared")
        return True