"""
Media API Endpoints
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.core.database import get_db
from app.models import MediaFile, MediaFileSchema, MediaFileCreate, MediaFileUpdate, MediaFileDownload, Movie

router = APIRouter()

@router.get("/", response_model=List[MediaFileSchema])
async def get_media_files(
    movie_id: int = Query(None),
    file_type: str = Query(None),
    is_downloaded: bool = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db)
):
    """Get media files with filters"""
    
    query = select(MediaFile)
    
    if movie_id:
        query = query.where(MediaFile.movie_id == movie_id)
    if file_type:
        query = query.where(MediaFile.file_type == file_type)
    if is_downloaded is not None:
        query = query.where(MediaFile.is_downloaded == is_downloaded)
    
    query = query.order_by(MediaFile.created_at.desc()).limit(limit)
    
    result = await db.execute(query)
    media_files = result.scalars().all()
    
    return media_files

@router.get("/{media_id}", response_model=MediaFileSchema)
async def get_media_file(media_id: int, db: AsyncSession = Depends(get_db)):
    """Get media file by ID"""
    
    result = await db.execute(select(MediaFile).where(MediaFile.id == media_id))
    media_file = result.scalar_one_or_none()
    
    if not media_file:
        raise HTTPException(status_code=404, detail="Media file not found")
    
    return media_file

@router.post("/", response_model=MediaFileSchema, status_code=201)
async def create_media_file(media_data: MediaFileCreate, db: AsyncSession = Depends(get_db)):
    """Create new media file"""
    
    # Check if movie exists
    movie_result = await db.execute(select(Movie).where(Movie.id == media_data.movie_id))
    if not movie_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Movie not found")
    
    # Check if media file already exists
    existing = await db.execute(
        select(MediaFile).where(
            and_(
                MediaFile.movie_id == media_data.movie_id,
                MediaFile.original_url == media_data.original_url
            )
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Media file already exists")
    
    media_file = MediaFile(**media_data.model_dump())
    db.add(media_file)
    await db.commit()
    await db.refresh(media_file)
    
    return media_file

@router.put("/{media_id}", response_model=MediaFileSchema)
async def update_media_file(
    media_id: int,
    media_data: MediaFileUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update media file"""
    
    result = await db.execute(select(MediaFile).where(MediaFile.id == media_id))
    media_file = result.scalar_one_or_none()
    
    if not media_file:
        raise HTTPException(status_code=404, detail="Media file not found")
    
    # Update fields
    update_data = media_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(media_file, field, value)
    
    await db.commit()
    await db.refresh(media_file)
    
    return media_file

@router.delete("/{media_id}")
async def delete_media_file(media_id: int, db: AsyncSession = Depends(get_db)):
    """Delete media file"""
    
    result = await db.execute(select(MediaFile).where(MediaFile.id == media_id))
    media_file = result.scalar_one_or_none()
    
    if not media_file:
        raise HTTPException(status_code=404, detail="Media file not found")
    
    await db.delete(media_file)
    await db.commit()
    
    return {"message": "Media file deleted successfully"}

@router.get("/movie/{movie_id}/images", response_model=List[MediaFileSchema])
async def get_movie_images(movie_id: int, db: AsyncSession = Depends(get_db)):
    """Get all images for a movie"""
    
    query = select(MediaFile).where(
        and_(
            MediaFile.movie_id == movie_id,
            MediaFile.file_type.in_(["poster", "still"])
        )
    ).order_by(MediaFile.file_type, MediaFile.created_at)
    
    result = await db.execute(query)
    images = result.scalars().all()
    
    return images

@router.get("/movie/{movie_id}/videos", response_model=List[MediaFileSchema])
async def get_movie_videos(movie_id: int, db: AsyncSession = Depends(get_db)):
    """Get all videos for a movie"""
    
    query = select(MediaFile).where(
        and_(
            MediaFile.movie_id == movie_id,
            MediaFile.file_type.in_(["trailer", "clip"])
        )
    ).order_by(MediaFile.file_type, MediaFile.created_at)
    
    result = await db.execute(query)
    videos = result.scalars().all()
    
    return videos

@router.get("/movie/{movie_id}/posters", response_model=List[MediaFileSchema])
async def get_movie_posters(movie_id: int, db: AsyncSession = Depends(get_db)):
    """Get movie posters"""
    
    query = select(MediaFile).where(
        and_(
            MediaFile.movie_id == movie_id,
            MediaFile.file_type == "poster"
        )
    ).order_by(MediaFile.quality.desc(), MediaFile.created_at)
    
    result = await db.execute(query)
    posters = result.scalars().all()
    
    return posters

@router.post("/download", status_code=202)
async def download_media_files(
    download_request: MediaFileDownload,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """Download media files in background"""
    
    # Verify media files exist
    media_files_query = select(MediaFile).where(
        MediaFile.id.in_(download_request.media_file_ids)
    )
    result = await db.execute(media_files_query)
    media_files = result.scalars().all()
    
    if len(media_files) != len(download_request.media_file_ids):
        raise HTTPException(status_code=404, detail="Some media files not found")
    
    # Add download task to background
    # background_tasks.add_task(download_media_task, download_request.media_file_ids)
    
    return {
        "message": "Download started",
        "media_files_count": len(media_files),
        "job_id": f"download_{len(media_files)}_files"
    }

@router.get("/stats/")
async def get_media_stats(db: AsyncSession = Depends(get_db)):
    """Get media file statistics"""
    
    # Total files by type
    from sqlalchemy import func
    
    type_stats = await db.execute(
        select(MediaFile.file_type, func.count(MediaFile.id))
        .group_by(MediaFile.file_type)
    )
    
    # Download status stats
    download_stats = await db.execute(
        select(MediaFile.is_downloaded, func.count(MediaFile.id))
        .group_by(MediaFile.is_downloaded)
    )
    
    # Total file size
    size_stats = await db.execute(
        select(func.sum(MediaFile.file_size))
        .where(MediaFile.file_size.is_not(None))
    )
    
    return {
        "by_type": dict(type_stats.fetchall()),
        "by_download_status": dict(download_stats.fetchall()),
        "total_size_bytes": size_stats.scalar() or 0
    }

@router.get("/failed/", response_model=List[MediaFileSchema])
async def get_failed_downloads(
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db)
):
    """Get failed media downloads"""
    
    query = select(MediaFile).where(
        MediaFile.download_failed == True
    ).order_by(MediaFile.updated_at.desc()).limit(limit)
    
    result = await db.execute(query)
    failed_files = result.scalars().all()
    
    return failed_files

@router.post("/{media_id}/retry-download", status_code=202)
async def retry_download(
    media_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """Retry downloading a failed media file"""
    
    result = await db.execute(select(MediaFile).where(MediaFile.id == media_id))
    media_file = result.scalar_one_or_none()
    
    if not media_file:
        raise HTTPException(status_code=404, detail="Media file not found")
    
    # Reset download status
    media_file.download_failed = False
    media_file.failure_reason = None
    await db.commit()
    
    # Add retry task to background
    # background_tasks.add_task(download_single_media_task, media_id)
    
    return {"message": "Download retry started", "media_id": media_id}