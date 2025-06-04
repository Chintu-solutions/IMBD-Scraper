"""
Movie API Endpoints
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from app.core.database import get_db
from app.models import Movie, MovieSchema, MovieDetail, MovieCreate, MovieUpdate, PaginatedResponse

router = APIRouter()

@router.get("/", response_model=PaginatedResponse[MovieSchema])
async def get_movies(
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
    year: int = Query(None, ge=1900, le=2030),
    genre: str = Query(None),
    min_rating: float = Query(None, ge=0.0, le=10.0),
    db: AsyncSession = Depends(get_db)
):
    """Get movies with pagination and filters"""
    
    # Build query with filters
    query = select(Movie)
    
    if year:
        query = query.where(Movie.year == year)
    if genre:
        query = query.where(Movie.genres.contains([genre]))
    if min_rating:
        query = query.where(Movie.imdb_rating >= min_rating)
    
    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Get paginated results
    offset = (page - 1) * size
    query = query.offset(offset).limit(size).order_by(Movie.year.desc(), Movie.imdb_rating.desc())
    
    result = await db.execute(query)
    movies = result.scalars().all()
    
    return PaginatedResponse(
        items=movies,
        total=total,
        page=page,
        size=size,
        has_next=offset + size < total,
        has_prev=page > 1
    )

@router.get("/{movie_id}", response_model=MovieDetail)
async def get_movie(movie_id: int, db: AsyncSession = Depends(get_db)):
    """Get movie by ID with details"""
    
    result = await db.execute(select(Movie).where(Movie.id == movie_id))
    movie = result.scalar_one_or_none()
    
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")
    
    return movie

@router.get("/imdb/{imdb_id}", response_model=MovieDetail)
async def get_movie_by_imdb_id(imdb_id: str, db: AsyncSession = Depends(get_db)):
    """Get movie by IMDb ID"""
    
    result = await db.execute(select(Movie).where(Movie.imdb_id == imdb_id))
    movie = result.scalar_one_or_none()
    
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")
    
    return movie

@router.post("/", response_model=MovieSchema, status_code=201)
async def create_movie(movie_data: MovieCreate, db: AsyncSession = Depends(get_db)):
    """Create new movie"""
    
    # Check if movie already exists
    existing = await db.execute(select(Movie).where(Movie.imdb_id == movie_data.imdb_id))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Movie already exists")
    
    movie = Movie(**movie_data.model_dump())
    db.add(movie)
    await db.commit()
    await db.refresh(movie)
    
    return movie

@router.put("/{movie_id}", response_model=MovieSchema)
async def update_movie(
    movie_id: int, 
    movie_data: MovieUpdate, 
    db: AsyncSession = Depends(get_db)
):
    """Update movie"""
    
    result = await db.execute(select(Movie).where(Movie.id == movie_id))
    movie = result.scalar_one_or_none()
    
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")
    
    # Update fields
    update_data = movie_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(movie, field, value)
    
    await db.commit()
    await db.refresh(movie)
    
    return movie

@router.delete("/{movie_id}")
async def delete_movie(movie_id: int, db: AsyncSession = Depends(get_db)):
    """Delete movie"""
    
    result = await db.execute(select(Movie).where(Movie.id == movie_id))
    movie = result.scalar_one_or_none()
    
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")
    
    await db.delete(movie)
    await db.commit()
    
    return {"message": "Movie deleted successfully"}

@router.get("/{movie_id}/cast")
async def get_movie_cast(movie_id: int, db: AsyncSession = Depends(get_db)):
    """Get movie cast and crew"""
    
    # Check if movie exists
    result = await db.execute(select(Movie).where(Movie.id == movie_id))
    movie = result.scalar_one_or_none()
    
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")
    
    # Get cast and crew from relationship
    # This would need the actual relationship query implementation
    return {"message": "Cast and crew data", "movie_id": movie_id}

@router.get("/top-rated/", response_model=List[MovieSchema])
async def get_top_rated_movies(
    limit: int = Query(10, ge=1, le=50),
    min_votes: int = Query(1000, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """Get top rated movies"""
    
    query = select(Movie).where(
        and_(
            Movie.imdb_rating.is_not(None),
            Movie.imdb_votes >= min_votes
        )
    ).order_by(Movie.imdb_rating.desc()).limit(limit)
    
    result = await db.execute(query)
    movies = result.scalars().all()
    
    return movies

@router.get("/recent/", response_model=List[MovieSchema])
async def get_recent_movies(
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db)
):
    """Get recently added movies"""
    
    query = select(Movie).order_by(Movie.created_at.desc()).limit(limit)
    
    result = await db.execute(query)
    movies = result.scalars().all()
    
    return movies