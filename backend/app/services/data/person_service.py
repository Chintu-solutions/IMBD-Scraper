"""
Person Service - Business logic for person operations
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import selectinload

from app.models import Person, Movie, PersonCreate, PersonUpdate
from app.core.logging import get_logger
from app.core.cache import get_cache_manager

logger = get_logger(__name__)

class PersonService:
    """Service for person business logic"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.cache = get_cache_manager()
    
    async def get_person_by_id(self, person_id: int) -> Optional[Person]:
        """Get person by ID with caching"""
        
        cache_key = f"person:id:{person_id}"
        
        # Try cache first
        if self.cache:
            cached_person = await self.cache.get(cache_key)
            if cached_person:
                logger.debug(f"Person {person_id} retrieved from cache")
                return Person(**cached_person)
        
        # Get from database
        result = await self.db.execute(
            select(Person)
            .options(selectinload(Person.movies))
            .where(Person.id == person_id)
        )
        person = result.scalar_one_or_none()
        
        # Cache if found
        if person and self.cache:
            person_data = {
                "id": person.id,
                "imdb_id": person.imdb_id,
                "name": person.name,
                "birth_date": person.birth_date.isoformat() if person.birth_date else None,
                "death_date": person.death_date.isoformat() if person.death_date else None,
                "birth_place": person.birth_place,
                "bio": person.bio,
                "primary_profession": person.primary_profession
            }
            await self.cache.set(cache_key, person_data, ttl=3600)
        
        return person
    
    async def get_person_by_imdb_id(self, imdb_id: str) -> Optional[Person]:
        """Get person by IMDb ID with caching"""
        
        cache_key = f"person:imdb:{imdb_id}"
        
        # Try cache first
        if self.cache:
            cached_person = await self.cache.get(cache_key)
            if cached_person:
                logger.debug(f"Person {imdb_id} retrieved from cache")
                return Person(**cached_person)
        
        # Get from database
        result = await self.db.execute(
            select(Person)
            .options(selectinload(Person.movies))
            .where(Person.imdb_id == imdb_id)
        )
        person = result.scalar_one_or_none()
        
        # Cache if found
        if person and self.cache:
            person_data = {
                "id": person.id,
                "imdb_id": person.imdb_id,
                "name": person.name,
                "birth_date": person.birth_date.isoformat() if person.birth_date else None,
                "death_date": person.death_date.isoformat() if person.death_date else None,
                "birth_place": person.birth_place,
                "bio": person.bio,
                "primary_profession": person.primary_profession
            }
            await self.cache.set(cache_key, person_data, ttl=3600)
        
        return person
    
    async def create_person(self, person_data: PersonCreate) -> Person:
        """Create new person"""
        
        # Check if person already exists
        existing = await self.get_person_by_imdb_id(person_data.imdb_id)
        if existing:
            raise ValueError(f"Person with IMDb ID {person_data.imdb_id} already exists")
        
        # Create person
        person = Person(**person_data.model_dump())
        self.db.add(person)
        await self.db.commit()
        await self.db.refresh(person)
        
        logger.info(f"Created person: {person.name} ({person.imdb_id})")
        return person
    
    async def update_person(self, person_id: int, person_data: PersonUpdate) -> Optional[Person]:
        """Update person"""
        
        person = await self.get_person_by_id(person_id)
        if not person:
            return None
        
        # Update fields
        update_data = person_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(person, field, value)
        
        await self.db.commit()
        await self.db.refresh(person)
        
        # Invalidate cache
        if self.cache:
            await self.cache.delete(f"person:id:{person_id}")
            await self.cache.delete(f"person:imdb:{person.imdb_id}")
        
        logger.info(f"Updated person: {person.name} ({person.imdb_id})")
        return person
    
    async def delete_person(self, person_id: int) -> bool:
        """Delete person"""
        
        person = await self.get_person_by_id(person_id)
        if not person:
            return False
        
        await self.db.delete(person)
        await self.db.commit()
        
        # Invalidate cache
        if self.cache:
            await self.cache.delete(f"person:id:{person_id}")
            await self.cache.delete(f"person:imdb:{person.imdb_id}")
        
        logger.info(f"Deleted person: {person.name} ({person.imdb_id})")
        return True
    
    async def get_people_paginated(
        self,
        page: int = 1,
        size: int = 50,
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Get paginated people with filters"""
        
        query = select(Person)
        
        # Apply filters
        if filters:
            if filters.get("name"):
                query = query.where(Person.name.ilike(f"%{filters['name']}%"))
            
            if filters.get("profession"):
                query = query.where(Person.primary_profession.contains([filters["profession"]]))
            
            if filters.get("birth_year"):
                # Extract year from birth_date
                query = query.where(func.extract('year', Person.birth_date) == filters["birth_year"])
        
        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()
        
        # Get paginated results
        offset = (page - 1) * size
        query = query.offset(offset).limit(size).order_by(Person.name)
        
        result = await self.db.execute(query)
        people = result.scalars().all()
        
        return {
            "items": people,
            "total": total,
            "page": page,
            "size": size,
            "has_next": offset + size < total,
            "has_prev": page > 1
        }
    
    async def search_people(self, query: str, limit: int = 20) -> List[Person]:
        """Search people by name"""
        
        search_query = select(Person).where(
            Person.name.ilike(f"%{query}%")
        ).order_by(Person.name).limit(limit)
        
        result = await self.db.execute(search_query)
        return result.scalars().all()
    
    async def get_directors(self, limit: int = 50) -> List[Person]:
        """Get directors"""
        
        query = select(Person).where(
            Person.primary_profession.contains(["director"])
        ).order_by(Person.name).limit(limit)
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def get_actors(self, limit: int = 50) -> List[Person]:
        """Get actors and actresses"""
        
        query = select(Person).where(
            or_(
                Person.primary_profession.contains(["actor"]),
                Person.primary_profession.contains(["actress"])
            )
        ).order_by(Person.name).limit(limit)
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def get_writers(self, limit: int = 50) -> List[Person]:
        """Get writers"""
        
        query = select(Person).where(
            Person.primary_profession.contains(["writer"])
        ).order_by(Person.name).limit(limit)
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def get_person_movies(self, person_id: int) -> List[Movie]:
        """Get movies for a person"""
        
        person = await self.get_person_by_id(person_id)
        if not person:
            return []
        
        # Get movies through relationship
        result = await self.db.execute(
            select(Person)
            .options(selectinload(Person.movies))
            .where(Person.id == person_id)
        )
        person_with_movies = result.scalar_one_or_none()
        
        return person_with_movies.movies if person_with_movies else []
    
    async def get_person_statistics(self) -> Dict[str, Any]:
        """Get person statistics"""
        
        # Total people
        total_people = await self.db.execute(select(func.count(Person.id)))
        
        # People by profession
        profession_stats = await self.db.execute(
            select(
                func.unnest(Person.primary_profession).label('profession'),
                func.count().label('count')
            ).where(Person.primary_profession.is_not(None))
            .group_by(func.unnest(Person.primary_profession))
            .order_by(func.count().desc())
            .limit(10)
        )
        
        # People with complete data
        complete_people = await self.db.execute(
            select(func.count(Person.id)).where(Person.is_complete == True)
        )
        
        return {
            "total_people": total_people.scalar() or 0,
            "complete_people": complete_people.scalar() or 0,
            "by_profession": dict(profession_stats.fetchall())
        }
    
    async def get_popular_people(self, limit: int = 20) -> List[Person]:
        """Get popular people based on known_for_titles"""
        
        query = select(Person).where(
            and_(
                Person.known_for_titles.is_not(None),
                func.array_length(Person.known_for_titles, 1) > 0
            )
        ).order_by(
            func.array_length(Person.known_for_titles, 1).desc()
        ).limit(limit)
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def update_person_completion_status(self, person_id: int, is_complete: bool) -> bool:
        """Update person completion status"""
        
        person = await self.get_person_by_id(person_id)
        if not person:
            return False
        
        person.is_complete = is_complete
        await self.db.commit()
        
        # Invalidate cache
        if self.cache:
            await self.cache.delete(f"person:id:{person_id}")
            await self.cache.delete(f"person:imdb:{person.imdb_id}")
        
        return True
    
    async def get_people_by_birth_year(self, year: int) -> List[Person]:
        """Get people born in a specific year"""
        
        query = select(Person).where(
            func.extract('year', Person.birth_date) == year
        ).order_by(Person.name)
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def get_living_people(self) -> List[Person]:
        """Get people who are still alive"""
        
        query = select(Person).where(
            and_(
                Person.birth_date.is_not(None),
                Person.death_date.is_(None)
            )
        ).order_by(Person.birth_date.desc())
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def bulk_update_people(self, updates: List[Dict[str, Any]]) -> int:
        """Bulk update multiple people"""
        
        updated_count = 0
        
        for update_data in updates:
            person_id = update_data.get("id")
            if not person_id:
                continue
            
            person = await self.get_person_by_id(person_id)
            if not person:
                continue
            
            # Update fields
            for field, value in update_data.items():
                if field != "id" and hasattr(person, field):
                    setattr(person, field, value)
            
            updated_count += 1
        
        await self.db.commit()
        
        # Clear person cache after bulk update
        if self.cache:
            await self.cache.delete_pattern("person:*")
        
        logger.info(f"Bulk updated {updated_count} people")
        return updated_count