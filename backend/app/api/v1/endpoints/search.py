"""
Search API Endpoints
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, text

from app.core.database import get_db
from app.models import Movie, Person, MovieSearchResult, PersonSchema

router = APIRouter()

@router.get("/movies", response_model=List[MovieSearchResult])
async def search_movies(
    q: str = Query(..., min_length=2, description="Search query"),
    year: Optional[int] = Query(None, ge=1900, le=2030),
    genre: Optional[str] = Query(None),
    min_rating: Optional[float] = Query(None, ge=0.0, le=10.0),
    max_rating: Optional[float] = Query(None, ge=0.0, le=10.0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """Search movies by title, genre, rating, etc."""
    
    # Base search query
    query = select(Movie).where(
        or_(
            Movie.title.ilike(f"%{q}%"),
            Movie.original_title.ilike(f"%{q}%")
        )
    )
    
    # Apply filters
    if year:
        query = query.where(Movie.year == year)
    if genre:
        query = query.where(Movie.genres.contains([genre]))
    if min_rating:
        query = query.where(Movie.imdb_rating >= min_rating)
    if max_rating:
        query = query.where(Movie.imdb_rating <= max_rating)
    
    # Order by relevance (rating and year)
    query = query.order_by(
        Movie.imdb_rating.desc().nulls_last(),
        Movie.year.desc().nulls_last()
    ).limit(limit)
    
    result = await db.execute(query)
    movies = result.scalars().all()
    
    return movies

@router.get("/people", response_model=List[PersonSchema])
async def search_people(
    q: str = Query(..., min_length=2, description="Search query"),
    profession: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """Search people by name"""
    
    query = select(Person).where(
        Person.name.ilike(f"%{q}%")
    )
    
    if profession:
        query = query.where(Person.primary_profession.contains([profession]))
    
    query = query.order_by(Person.name).limit(limit)
    
    result = await db.execute(query)
    people = result.scalars().all()
    
    return people

@router.get("/advanced-movies", response_model=List[MovieSearchResult])
async def advanced_movie_search(
    title: Optional[str] = Query(None, min_length=2),
    year_start: Optional[int] = Query(None, ge=1900, le=2030),
    year_end: Optional[int] = Query(None, ge=1900, le=2030),
    rating_min: Optional[float] = Query(None, ge=0.0, le=10.0),
    rating_max: Optional[float] = Query(None, ge=0.0, le=10.0),
    genres: Optional[str] = Query(None, description="Comma-separated genres"),
    mpaa_rating: Optional[str] = Query(None),
    min_votes: Optional[int] = Query(None, ge=0),
    runtime_min: Optional[int] = Query(None, ge=1),
    runtime_max: Optional[int] = Query(None, ge=1),
    sort_by: str = Query("rating", regex="^(rating|year|title|votes)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
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
        genre_list = [g.strip() for g in genres.split(",")]
        for genre in genre_list:
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
    
    result = await db.execute(query)
    movies = result.scalars().all()
    
    return movies

@router.get("/genres")
async def get_available_genres(db: AsyncSession = Depends(get_db)):
    """Get all available genres from movies"""
    
    # Get all unique genres
    result = await db.execute(
        select(func.unnest(Movie.genres).label('genre'))
        .where(Movie.genres.is_not(None))
        .distinct()
    )
    
    genres = [row[0] for row in result.fetchall()]
    genres.sort()
    
    return {"genres": genres}

@router.get("/years")
async def get_available_years(db: AsyncSession = Depends(get_db)):
    """Get available year range from movies"""
    
    result = await db.execute(
        select(
            func.min(Movie.year).label('min_year'),
            func.max(Movie.year).label('max_year')
        ).where(Movie.year.is_not(None))
    )
    
    row = result.fetchone()
    
    return {
        "min_year": row[0] if row else None,
        "max_year": row[1] if row else None
    }

@router.get("/suggestions")
async def get_search_suggestions(
    q: str = Query(..., min_length=1),
    type: str = Query("movie", regex="^(movie|person)$"),
    limit: int = Query(10, ge=1, le=20),
    db: AsyncSession = Depends(get_db)
):
    """Get search suggestions for autocomplete"""
    
    if type == "movie":
        query = select(Movie.title).where(
            Movie.title.ilike(f"{q}%")
        ).order_by(
            Movie.imdb_rating.desc().nulls_last()
        ).limit(limit)
        
        result = await db.execute(query)
        suggestions = [row[0] for row in result.fetchall()]
    
    else:  # person
        query = select(Person.name).where(
            Person.name.ilike(f"{q}%")
        ).order_by(Person.name).limit(limit)
        
        result = await db.execute(query)
        suggestions = [row[0] for row in result.fetchall()]
    
    return {"suggestions": suggestions}

@router.get("/similar/{movie_id}")
async def get_similar_movies(
    movie_id: int,
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db)
):
    """Get movies similar to the given movie"""
    
    # Get the reference movie
    movie_result = await db.execute(select(Movie).where(Movie.id == movie_id))
    movie = movie_result.scalar_one_or_none()
    
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")
    
    # Find similar movies based on genres and year
    query = select(Movie).where(
        and_(
            Movie.id != movie_id,  # Exclude the same movie
            Movie.genres.overlap(movie.genres or []),  # Same genres
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
    
    result = await db.execute(query)
    similar_movies = result.scalars().all()
    
    return similar_movies

@router.get("/trending")
async def get_trending_movies(
    period: str = Query("week", regex="^(day|week|month)$"),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
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
    
    result = await db.execute(query)
    trending_movies = result.scalars().all()
    
    return trending_movies

@router.get("/stats")
async def get_search_stats(db: AsyncSession = Depends(get_db)):
    """Get general database statistics for search"""
    
    # Movie stats
    movie_stats = await db.execute(
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
    person_stats = await db.execute(
        select(func.count(Person.id).label('total_people'))
    )
    person_row = person_stats.fetchone()
    
    # Genre distribution
    genre_stats = await db.execute(
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
        "top_genres": top_genres
    }