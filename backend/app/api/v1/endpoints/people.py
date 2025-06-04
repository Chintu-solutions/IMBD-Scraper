"""
People API Endpoints
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_

from app.core.database import get_db
from app.models import Person, PersonSchema, PersonDetail, PersonCreate, PersonUpdate, PaginatedResponse

router = APIRouter()

@router.get("/", response_model=PaginatedResponse[PersonSchema])
async def get_people(
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
    name: str = Query(None, min_length=2),
    profession: str = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """Get people with pagination and filters"""
    
    # Build query with filters
    query = select(Person)
    
    if name:
        query = query.where(Person.name.ilike(f"%{name}%"))
    if profession:
        query = query.where(Person.primary_profession.contains([profession]))
    
    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Get paginated results
    offset = (page - 1) * size
    query = query.offset(offset).limit(size).order_by(Person.name)
    
    result = await db.execute(query)
    people = result.scalars().all()
    
    return PaginatedResponse(
        items=people,
        total=total,
        page=page,
        size=size,
        has_next=offset + size < total,
        has_prev=page > 1
    )

@router.get("/{person_id}", response_model=PersonDetail)
async def get_person(person_id: int, db: AsyncSession = Depends(get_db)):
    """Get person by ID with details"""
    
    result = await db.execute(select(Person).where(Person.id == person_id))
    person = result.scalar_one_or_none()
    
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    
    return person

@router.get("/imdb/{imdb_id}", response_model=PersonDetail)
async def get_person_by_imdb_id(imdb_id: str, db: AsyncSession = Depends(get_db)):
    """Get person by IMDb ID"""
    
    result = await db.execute(select(Person).where(Person.imdb_id == imdb_id))
    person = result.scalar_one_or_none()
    
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    
    return person

@router.post("/", response_model=PersonSchema, status_code=201)
async def create_person(person_data: PersonCreate, db: AsyncSession = Depends(get_db)):
    """Create new person"""
    
    # Check if person already exists
    existing = await db.execute(select(Person).where(Person.imdb_id == person_data.imdb_id))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Person already exists")
    
    person = Person(**person_data.model_dump())
    db.add(person)
    await db.commit()
    await db.refresh(person)
    
    return person

@router.put("/{person_id}", response_model=PersonSchema)
async def update_person(
    person_id: int, 
    person_data: PersonUpdate, 
    db: AsyncSession = Depends(get_db)
):
    """Update person"""
    
    result = await db.execute(select(Person).where(Person.id == person_id))
    person = result.scalar_one_or_none()
    
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    
    # Update fields
    update_data = person_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(person, field, value)
    
    await db.commit()
    await db.refresh(person)
    
    return person

@router.delete("/{person_id}")
async def delete_person(person_id: int, db: AsyncSession = Depends(get_db)):
    """Delete person"""
    
    result = await db.execute(select(Person).where(Person.id == person_id))
    person = result.scalar_one_or_none()
    
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    
    await db.delete(person)
    await db.commit()
    
    return {"message": "Person deleted successfully"}

@router.get("/{person_id}/movies")
async def get_person_movies(person_id: int, db: AsyncSession = Depends(get_db)):
    """Get movies for a person"""
    
    # Check if person exists
    result = await db.execute(select(Person).where(Person.id == person_id))
    person = result.scalar_one_or_none()
    
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    
    # Get movies from relationship
    return {"message": "Person movies", "person_id": person_id}

@router.get("/search/", response_model=List[PersonSchema])
async def search_people(
    q: str = Query(..., min_length=2),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db)
):
    """Search people by name"""
    
    query = select(Person).where(
        Person.name.ilike(f"%{q}%")
    ).order_by(Person.name).limit(limit)
    
    result = await db.execute(query)
    people = result.scalars().all()
    
    return people

@router.get("/directors/", response_model=List[PersonSchema])
async def get_directors(
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db)
):
    """Get directors"""
    
    query = select(Person).where(
        Person.primary_profession.contains(["director"])
    ).limit(limit)
    
    result = await db.execute(query)
    directors = result.scalars().all()
    
    return directors

@router.get("/actors/", response_model=List[PersonSchema])
async def get_actors(
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db)
):
    """Get actors"""
    
    query = select(Person).where(
        or_(
            Person.primary_profession.contains(["actor"]),
            Person.primary_profession.contains(["actress"])
        )
    ).limit(limit)
    
    result = await db.execute(query)
    actors = result.scalars().all()
    
    return actors