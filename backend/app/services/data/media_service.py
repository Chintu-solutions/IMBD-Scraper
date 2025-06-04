"""
Media Service - Business logic for media file operations
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import selectinload

from app.models import MediaFile, Movie, MediaFileCreate, MediaFileUpdate
from app.core.logging import get_logger
from app.core.cache import get_cache_manager

logger = get_logger(__name__)

class MediaService:
    """Service for media file business logic"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.cache = get_cache_manager()
    
    async def get_media_file_by_id(self, media_id: int) -> Optional[MediaFile]:
        """Get media file by ID"""
        
        result = await self.db.execute(
            select(MediaFile)
            .options(selectinload(MediaFile.movie))
            .where(MediaFile.id == media_id)
        )
        return result.scalar_one_or_none()
    
    async def create_media_file(self, media_data: MediaFileCreate) -> MediaFile:
        """Create new media file"""
        
        # Check if movie exists
        movie_result = await self.db.execute(select(Movie).where(Movie.id == media_data.movie_id))
        if not movie_result.scalar_one_or_none():
            raise ValueError(f"Movie with ID {media_data.movie_id} not found")
        
        # Check if media file already exists (same URL for same movie)
        existing = await self.db.execute(
            select(MediaFile).where(
                and_(
                    MediaFile.movie_id == media_data.movie_id,
                    MediaFile.original_url == media_data.original_url
                )
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError("Media file with this URL already exists for this movie")
        
        # Create media file
        media_file = MediaFile(**media_data.model_dump())
        self.db.add(media_file)
        await self.db.commit()
        await self.db.refresh(media_file)
        
        logger.info(f"Created media file: {media_file.file_type} for movie {media_data.movie_id}")
        return media_file
    
    async def update_media_file(self, media_id: int, media_data: MediaFileUpdate) -> Optional[MediaFile]:
        """Update media file"""
        
        media_file = await self.get_media_file_by_id(media_id)
        if not media_file:
            return None
        
        # Update fields
        update_data = media_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(media_file, field, value)
        
        await self.db.commit()
        await self.db.refresh(media_file)
        
        logger.info(f"Updated media file: {media_file.id}")
        return media_file
    
    async def delete_media_file(self, media_id: int) -> bool:
        """Delete media file"""
        
        media_file = await self.get_media_file_by_id(media_id)
        if not media_file:
            return False
        
        await self.db.delete(media_file)
        await self.db.commit()
        
        logger.info(f"Deleted media file: {media_id}")
        return True
    
    async def get_media_files_paginated(
        self,
        page: int = 1,
        size: int = 50,
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Get paginated media files with filters"""
        
        query = select(MediaFile)
        
        # Apply filters
        if filters:
            if filters.get("movie_id"):
                query = query.where(MediaFile.movie_id == filters["movie_id"])
            
            if filters.get("file_type"):
                query = query.where(MediaFile.file_type == filters["file_type"])
            
            if filters.get("is_downloaded") is not None:
                query = query.where(MediaFile.is_downloaded == filters["is_downloaded"])
            
            if filters.get("download_failed") is not None:
                query = query.where(MediaFile.download_failed == filters["download_failed"])
            
            if filters.get("quality"):
                query = query.where(MediaFile.quality == filters["quality"])
        
        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()
        
        # Get paginated results
        offset = (page - 1) * size
        query = query.offset(offset).limit(size).order_by(MediaFile.created_at.desc())
        
        result = await self.db.execute(query)
        media_files = result.scalars().all()
        
        return {
            "items": media_files,
            "total": total,
            "page": page,
            "size": size,
            "has_next": offset + size < total,
            "has_prev": page > 1
        }
    
    async def get_movie_media_files(self, movie_id: int, file_type: Optional[str] = None) -> List[MediaFile]:
        """Get all media files for a movie"""
        
        query = select(MediaFile).where(MediaFile.movie_id == movie_id)
        
        if file_type:
            query = query.where(MediaFile.file_type == file_type)
        
        query = query.order_by(MediaFile.file_type, MediaFile.created_at)
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def get_movie_images(self, movie_id: int) -> List[MediaFile]:
        """Get all images for a movie (posters and stills)"""
        
        query = select(MediaFile).where(
            and_(
                MediaFile.movie_id == movie_id,
                MediaFile.file_type.in_(["poster", "still"])
            )
        ).order_by(MediaFile.file_type, MediaFile.quality.desc())
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def get_movie_videos(self, movie_id: int) -> List[MediaFile]:
        """Get all videos for a movie (trailers and clips)"""
        
        query = select(MediaFile).where(
            and_(
                MediaFile.movie_id == movie_id,
                MediaFile.file_type.in_(["trailer", "clip"])
            )
        ).order_by(MediaFile.file_type, MediaFile.duration.desc())
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def get_movie_posters(self, movie_id: int) -> List[MediaFile]:
        """Get movie posters sorted by quality"""
        
        query = select(MediaFile).where(
            and_(
                MediaFile.movie_id == movie_id,
                MediaFile.file_type == "poster"
            )
        ).order_by(MediaFile.quality.desc(), MediaFile.width.desc())
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def get_best_poster(self, movie_id: int) -> Optional[MediaFile]:
        """Get the best quality poster for a movie"""
        
        query = select(MediaFile).where(
            and_(
                MediaFile.movie_id == movie_id,
                MediaFile.file_type == "poster",
                MediaFile.is_downloaded == True
            )
        ).order_by(MediaFile.quality.desc(), MediaFile.width.desc()).limit(1)
        
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_pending_downloads(self, limit: int = 100) -> List[MediaFile]:
        """Get media files pending download"""
        
        query = select(MediaFile).where(
            and_(
                MediaFile.is_downloaded == False,
                MediaFile.download_failed == False
            )
        ).order_by(MediaFile.created_at).limit(limit)
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def get_failed_downloads(self, limit: int = 50) -> List[MediaFile]:
        """Get failed media downloads"""
        
        query = select(MediaFile).where(
            MediaFile.download_failed == True
        ).order_by(MediaFile.updated_at.desc()).limit(limit)
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def mark_download_success(self, media_id: int, local_path: str, file_size: int) -> bool:
        """Mark media file as successfully downloaded"""
        
        media_file = await self.get_media_file_by_id(media_id)
        if not media_file:
            return False
        
        media_file.is_downloaded = True
        media_file.download_failed = False
        media_file.local_path = local_path
        media_file.file_size = file_size
        media_file.failure_reason = None
        
        await self.db.commit()
        
        logger.info(f"Marked media file {media_id} as downloaded: {local_path}")
        return True
    
    async def mark_download_failed(self, media_id: int, reason: str) -> bool:
        """Mark media file download as failed"""
        
        media_file = await self.get_media_file_by_id(media_id)
        if not media_file:
            return False
        
        media_file.download_failed = True
        media_file.failure_reason = reason
        
        await self.db.commit()
        
        logger.warning(f"Marked media file {media_id} download as failed: {reason}")
        return True
    
    async def retry_failed_download(self, media_id: int) -> bool:
        """Reset failed download for retry"""
        
        media_file = await self.get_media_file_by_id(media_id)
        if not media_file:
            return False
        
        media_file.download_failed = False
        media_file.failure_reason = None
        
        await self.db.commit()
        
        logger.info(f"Reset media file {media_id} for download retry")
        return True
    
    async def get_media_statistics(self) -> Dict[str, Any]:
        """Get media file statistics"""
        
        # Total files by type
        type_stats = await self.db.execute(
            select(MediaFile.file_type, func.count(MediaFile.id))
            .group_by(MediaFile.file_type)
        )
        
        # Download status stats
        download_stats = await self.db.execute(
            select(MediaFile.is_downloaded, func.count(MediaFile.id))
            .group_by(MediaFile.is_downloaded)
        )
        
        # Failed downloads
        failed_stats = await self.db.execute(
            select(MediaFile.download_failed, func.count(MediaFile.id))
            .group_by(MediaFile.download_failed)
        )
        
        # Total file size
        size_stats = await self.db.execute(
            select(func.sum(MediaFile.file_size))
            .where(MediaFile.file_size.is_not(None))
        )
        
        # Average file size by type
        avg_size_stats = await self.db.execute(
            select(MediaFile.file_type, func.avg(MediaFile.file_size))
            .where(MediaFile.file_size.is_not(None))
            .group_by(MediaFile.file_type)
        )
        
        return {
            "by_type": dict(type_stats.fetchall()),
            "by_download_status": dict(download_stats.fetchall()),
            "by_failure_status": dict(failed_stats.fetchall()),
            "total_size_bytes": size_stats.scalar() or 0,
            "average_size_by_type": dict(avg_size_stats.fetchall())
        }
    
    async def clean_orphaned_media(self) -> int:
        """Remove media files for non-existent movies"""
        
        # Find media files with invalid movie_id
        orphaned_query = select(MediaFile.id).where(
            MediaFile.movie_id.notin_(select(Movie.id))
        )
        
        result = await self.db.execute(orphaned_query)
        orphaned_ids = [row[0] for row in result.fetchall()]
        
        if orphaned_ids:
            # Delete orphaned media files
            delete_query = select(MediaFile).where(MediaFile.id.in_(orphaned_ids))
            orphaned_files = await self.db.execute(delete_query)
            
            for media_file in orphaned_files.scalars():
                await self.db.delete(media_file)
            
            await self.db.commit()
            
            logger.info(f"Cleaned {len(orphaned_ids)} orphaned media files")
        
        return len(orphaned_ids)
    
    async def bulk_create_media_files(self, media_files_data: List[MediaFileCreate]) -> List[MediaFile]:
        """Bulk create multiple media files"""
        
        media_files = []
        
        for media_data in media_files_data:
            try:
                # Check if movie exists
                movie_result = await self.db.execute(
                    select(Movie).where(Movie.id == media_data.movie_id)
                )
                if not movie_result.scalar_one_or_none():
                    logger.warning(f"Skipping media file: Movie {media_data.movie_id} not found")
                    continue
                
                # Check for duplicates
                existing = await self.db.execute(
                    select(MediaFile).where(
                        and_(
                            MediaFile.movie_id == media_data.movie_id,
                            MediaFile.original_url == media_data.original_url
                        )
                    )
                )
                if existing.scalar_one_or_none():
                    logger.debug(f"Skipping duplicate media file: {media_data.original_url}")
                    continue
                
                # Create media file
                media_file = MediaFile(**media_data.model_dump())
                self.db.add(media_file)
                media_files.append(media_file)
                
            except Exception as e:
                logger.error(f"Error creating media file: {e}")
                continue
        
        await self.db.commit()
        
        # Refresh all created files
        for media_file in media_files:
            await self.db.refresh(media_file)
        
        logger.info(f"Bulk created {len(media_files)} media files")
        return media_files
    
    async def get_download_queue_status(self) -> Dict[str, int]:
        """Get download queue status"""
        
        pending = await self.db.execute(
            select(func.count(MediaFile.id)).where(
                and_(
                    MediaFile.is_downloaded == False,
                    MediaFile.download_failed == False
                )
            )
        )
        
        downloading = await self.db.execute(
            select(func.count(MediaFile.id)).where(
                MediaFile.is_downloaded == False
            )
        )
        
        completed = await self.db.execute(
            select(func.count(MediaFile.id)).where(
                MediaFile.is_downloaded == True
            )
        )
        
        failed = await self.db.execute(
            select(func.count(MediaFile.id)).where(
                MediaFile.download_failed == True
            )
        )
        
        return {
            "pending": pending.scalar() or 0,
            "downloading": downloading.scalar() or 0,
            "completed": completed.scalar() or 0,
            "failed": failed.scalar() or 0
        }