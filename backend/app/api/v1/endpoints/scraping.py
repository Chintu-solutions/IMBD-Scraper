"""
Scraping API Endpoints
"""

from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.cache import scraping_cache
from app.core.security import generate_job_id
from app.models import FilterConfig, ProxyConfig, ScrapeJobConfig, BaseResponse

router = APIRouter()

@router.post("/start", response_model=Dict[str, Any])
async def start_scraping_job(
    job_config: ScrapeJobConfig,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """Start a new scraping job"""
    
    # Generate unique job ID
    job_id = generate_job_id()
    
    # Validate configuration
    if job_config.filters.max_pages > 20:
        raise HTTPException(
            status_code=400, 
            detail="Maximum 20 pages allowed per job"
        )
    
    # Cache job configuration
    job_data = {
        "job_id": job_id,
        "status": "queued",
        "filters": job_config.filters.model_dump(),
        "proxy": job_config.proxy.model_dump() if job_config.proxy else None,
        "download_media": job_config.download_media,
        "max_concurrent": job_config.max_concurrent,
        "created_at": "2024-01-01T00:00:00Z",  # Would use datetime.utcnow()
        "started_at": None,
        "completed_at": None,
        "progress": {
            "pages_scraped": 0,
            "movies_found": 0,
            "movies_saved": 0,
            "media_downloaded": 0,
            "errors": 0
        }
    }
    
    if scraping_cache:
        await scraping_cache.cache_job_status(job_id, job_data)
    
    # Add scraping task to background queue
    # background_tasks.add_task(run_scraping_job, job_id, job_config)
    
    return {
        "job_id": job_id,
        "status": "queued",
        "message": "Scraping job started successfully",
        "estimated_duration_minutes": job_config.filters.max_pages * 2
    }

@router.get("/jobs/{job_id}", response_model=Dict[str, Any])
async def get_job_status(job_id: str):
    """Get scraping job status"""
    
    if not scraping_cache:
        raise HTTPException(status_code=503, detail="Cache service unavailable")
    
    job_data = await scraping_cache.get_job_status(job_id)
    
    if not job_data:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return job_data

@router.post("/jobs/{job_id}/stop")
async def stop_scraping_job(job_id: str):
    """Stop a running scraping job"""
    
    if not scraping_cache:
        raise HTTPException(status_code=503, detail="Cache service unavailable")
    
    job_data = await scraping_cache.get_job_status(job_id)
    
    if not job_data:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job_data.get("status") not in ["queued", "running"]:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot stop job with status: {job_data.get('status')}"
        )
    
    # Update job status to stopped
    job_data["status"] = "stopped"
    job_data["completed_at"] = "2024-01-01T00:00:00Z"  # Would use datetime.utcnow()
    
    await scraping_cache.cache_job_status(job_id, job_data)
    
    return {"message": "Job stopped successfully", "job_id": job_id}

@router.get("/jobs", response_model=List[Dict[str, Any]])
async def list_scraping_jobs(
    status: str = None,
    limit: int = 50
):
    """List recent scraping jobs"""
    
    # In a real implementation, this would query the cache or database
    # for recent jobs, optionally filtered by status
    
    sample_jobs = [
        {
            "job_id": "job_1234567890_abcdef12",
            "status": "completed",
            "created_at": "2024-01-01T10:00:00Z",
            "completed_at": "2024-01-01T10:15:00Z",
            "progress": {
                "pages_scraped": 3,
                "movies_found": 150,
                "movies_saved": 148,
                "media_downloaded": 445,
                "errors": 2
            }
        },
        {
            "job_id": "job_1234567891_bcdef123",
            "status": "running",
            "created_at": "2024-01-01T11:00:00Z",
            "started_at": "2024-01-01T11:01:00Z",
            "progress": {
                "pages_scraped": 1,
                "movies_found": 42,
                "movies_saved": 40,
                "media_downloaded": 120,
                "errors": 0
            }
        }
    ]
    
    if status:
        sample_jobs = [job for job in sample_jobs if job["status"] == status]
    
    return sample_jobs[:limit]

@router.delete("/jobs/{job_id}")
async def delete_job(job_id: str):
    """Delete a scraping job record"""
    
    if not scraping_cache:
        raise HTTPException(status_code=503, detail="Cache service unavailable")
    
    job_data = await scraping_cache.get_job_status(job_id)
    
    if not job_data:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job_data.get("status") in ["queued", "running"]:
        raise HTTPException(
            status_code=400, 
            detail="Cannot delete running job. Stop it first."
        )
    
    # Delete from cache (in real implementation, also from database)
    # await scraping_cache.delete(f"job:{job_id}")
    
    return {"message": "Job deleted successfully"}

@router.get("/stats")
async def get_scraping_stats():
    """Get overall scraping statistics"""
    
    # In a real implementation, this would aggregate data from database
    return {
        "total_jobs": 25,
        "completed_jobs": 20,
        "running_jobs": 2,
        "failed_jobs": 3,
        "total_movies_scraped": 5250,
        "total_media_downloaded": 15750,
        "average_job_duration_minutes": 12.5,
        "success_rate": 0.88
    }

@router.post("/validate-proxy")
async def validate_proxy_config(proxy_config: ProxyConfig):
    """Validate proxy configuration"""
    
    if not proxy_config.host or not proxy_config.port:
        raise HTTPException(status_code=400, detail="Host and port are required")
    
    if not proxy_config.ipstack_api_key:
        return {"valid": False, "message": "ipstack API key required for validation"}
    
    # In real implementation, would test proxy connectivity
    # and validate IP geolocation using ipstack API
    
    validation_result = {
        "valid": True,
        "ip_address": "192.168.1.100",  # Mock data
        "country": "United States",
        "city": "New York",
        "isp": "Example ISP",
        "response_time_ms": 150
    }
    
    # Cache validation result if valid
    if scraping_cache and validation_result["valid"]:
        await scraping_cache.cache_proxy_validation(
            proxy_config.host, 
            validation_result
        )
    
    return validation_result

@router.get("/proxy-validation/{proxy_host}")
async def get_cached_proxy_validation(proxy_host: str):
    """Get cached proxy validation result"""
    
    if not scraping_cache:
        raise HTTPException(status_code=503, detail="Cache service unavailable")
    
    validation_data = await scraping_cache.get_proxy_validation(proxy_host)
    
    if not validation_data:
        raise HTTPException(status_code=404, detail="No validation data found")
    
    return validation_data

@router.post("/test-scrape")
async def test_scraping_setup(
    filters: FilterConfig,
    proxy: ProxyConfig = None
):
    """Test scraping setup without actually scraping"""
    
    # Validate filters
    issues = []
    
    if filters.max_pages > 5:
        issues.append("Test scraping limited to 5 pages")
        filters.max_pages = 5
    
    if filters.year_start and filters.year_end:
        if filters.year_start > filters.year_end:
            issues.append("Start year cannot be greater than end year")
    
    if filters.rating_min and filters.rating_max:
        if filters.rating_min > filters.rating_max:
            issues.append("Minimum rating cannot be greater than maximum rating")
    
    # Test proxy if provided
    proxy_status = "not_configured"
    if proxy and proxy.host and proxy.port:
        proxy_status = "configured"
        if proxy.ipstack_api_key:
            proxy_status = "configured_with_validation"
    
    return {
        "status": "ready" if not issues else "ready_with_warnings",
        "issues": issues,
        "estimated_movies": filters.max_pages * 50,  # Rough estimate
        "estimated_duration_minutes": filters.max_pages * 2,
        "proxy_status": proxy_status,
        "filters_summary": {
            "pages": filters.max_pages,
            "year_range": f"{filters.year_start or 'any'}-{filters.year_end or 'any'}",
            "rating_range": f"{filters.rating_min or 0.0}-{filters.rating_max or 10.0}",
            "genres": filters.genres or ["all"],
            "sort": f"{filters.sort_by} {filters.sort_order}"
        }
    }

@router.get("/queue-status")
async def get_queue_status():
    """Get scraping queue status"""
    
    # In real implementation, would check Celery queue status
    return {
        "queue_name": "scraping",
        "pending_jobs": 2,
        "active_jobs": 1,
        "failed_jobs": 0,
        "worker_count": 3,
        "estimated_wait_time_minutes": 5
    }