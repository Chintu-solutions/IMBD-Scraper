"""
Seed database with sample data for development
"""
import asyncio
from datetime import datetime, date
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models.database.movie import Movie
from app.models.database.person import Person

async def seed_data():
    """Add sample data to the database"""
    async with AsyncSessionLocal() as session:
        # Sample movies
        movies = [
            Movie(
                imdb_id="tt0111161",
                title="The Shawshank Redemption",
                original_title="The Shawshank Redemption",
                year=1994,
                release_date=date(1994, 9, 23),
                runtime=142,
                imdb_rating=9.3,
                plot="Two imprisoned men bond over a number of years...",
                mpaa_rating="R",
            ),
            Movie(
                imdb_id="tt0068646",
                title="The Godfather",
                original_title="The Godfather",
                year=1972,
                release_date=date(1972, 3, 24),
                runtime=175,
                imdb_rating=9.2,
                plot="The aging patriarch of an organized crime dynasty...",
                mpaa_rating="R",
            ),
        ]
        
        for movie in movies:
            session.add(movie)
        
        await session.commit()
        print("✅ Sample data added successfully!")

if __name__ == "__main__":
    asyncio.run(seed_data())
