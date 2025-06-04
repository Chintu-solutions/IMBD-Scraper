"""
Media Downloader - Download and manage movie media files
"""

import asyncio
import aiohttp
import aiofiles
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from urllib.parse import urlparse, unquote
import hashlib
from datetime import datetime
import mimetypes

from app.core.logging import get_logger
from app.core.config import settings
from app.services.external.storage_service import StorageService
from app.services.scraping.proxy_manager import ProxyManager

logger = get_logger(__name__)

class MediaDownloader:
    """Download and manage movie media files"""
    
    def __init__(self, proxy_manager: Optional[ProxyManager] = None):
        self.proxy_manager = proxy_manager
        self.storage_service = StorageService()
        self.concurrent_downloads = 5
        self.download_timeout = 30
        self.max_file_size = 100 * 1024 * 1024  # 100MB
        self.retry_attempts = 3
        self.download_stats = {
            "total_downloads": 0,
            "successful_downloads": 0,
            "failed_downloads": 0,
            "total_bytes": 0
        }
    
    async def download_media_file(
        self,
        url: str,
        movie_id: int,
        file_type: str,
        quality: str = "original",
        force_download: bool = False
    ) -> Dict[str, Any]:
        """Download a single media file"""
        
        download_result = {
            "success": False,
            "url": url,
            "movie_id": movie_id,
            "file_type": file_type,
            "local_path": None,
            "file_size": 0,
            "error": None,
            "download_time": 0
        }
        
        start_time = asyncio.get_event_loop().time()
        
        try:
            # Validate URL
            if not self._is_valid_url(url):
                raise ValueError(f"Invalid URL: {url}")
            
            # Generate filename
            filename = self._generate_filename(url, movie_id, file_type, quality)
            
            # Check if file already exists
            if not force_download:
                existing_file = await self._check_existing_file(filename, movie_id)
                if existing_file:
                    download_result.update(existing_file)
                    download_result["success"] = True
                    return download_result
            
            # Download file
            file_data, file_info = await self._download_file_data(url)
            
            if not file_data:
                raise ValueError("No data downloaded")
            
            # Validate file size
            if len(file_data) > self.max_file_size:
                raise ValueError(f"File too large: {len(file_data)} bytes")
            
            # Save file using storage service
            save_result = await self.storage_service.save_downloaded_media(
                file_data=file_data,
                original_url=url,
                movie_id=movie_id,
                file_type=file_type,
                file_extension=file_info.get("extension")
            )
            
            if save_result["success"]:
                download_result.update({
                    "success": True,
                    "local_path": save_result["local_path"],
                    "filename": save_result["filename"],
                    "file_size": save_result["file_size"],
                    "file_hash": save_result["file_hash"],
                    "mime_type": save_result["mime_type"]
                })
                
                # Update stats
                self.download_stats["successful_downloads"] += 1
                self.download_stats["total_bytes"] += save_result["file_size"]
            else:
                raise ValueError(f"Failed to save file: {save_result['error']}")
            
        except Exception as e:
            download_result["error"] = str(e)
            self.download_stats["failed_downloads"] += 1
            logger.error(f"Failed to download {url}: {e}")
        
        finally:
            download_result["download_time"] = asyncio.get_event_loop().time() - start_time
            self.download_stats["total_downloads"] += 1
        
        return download_result
    
    async def _download_file_data(self, url: str) -> Tuple[Optional[bytes], Dict[str, Any]]:
        """Download file data with retry logic"""
        
        file_info = {
            "extension": None,
            "content_type": None,
            "content_length": None
        }
        
        for attempt in range(self.retry_attempts):
            try:
                # Setup session with proxy if available
                connector = aiohttp.TCPConnector(ssl=False)
                timeout = aiohttp.ClientTimeout(total=self.download_timeout)
                
                proxy_url = None
                if self.proxy_manager:
                    proxy = self.proxy_manager.get_current_proxy()
                    if proxy:
                        proxy_url = self.proxy_manager.get_proxy_url(proxy)
                
                async with aiohttp.ClientSession(
                    connector=connector,
                    timeout=timeout
                ) as session:
                    
                    headers = {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                        "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
                        "Accept-Encoding": "gzip, deflate, br",
                        "Accept-Language": "en-US,en;q=0.9",
                        "Cache-Control": "no-cache",
                        "Pragma": "no-cache"
                    }
                    
                    async with session.get(
                        url,
                        headers=headers,
                        proxy=proxy_url
                    ) as response:
                        
                        if response.status == 200:
                            # Get file info from headers
                            file_info["content_type"] = response.headers.get("Content-Type")
                            file_info["content_length"] = response.headers.get("Content-Length")
                            
                            # Determine file extension
                            file_info["extension"] = self._get_file_extension(url, file_info["content_type"])
                            
                            # Check file size before downloading
                            if file_info["content_length"]:
                                content_length = int(file_info["content_length"])
                                if content_length > self.max_file_size:
                                    raise ValueError(f"File too large: {content_length} bytes")
                            
                            # Download file data
                            file_data = await response.read()
                            
                            # Mark proxy as successful if used
                            if self.proxy_manager and proxy:
                                self.proxy_manager.mark_proxy_success(proxy)
                            
                            return file_data, file_info
                        else:
                            raise aiohttp.ClientResponseError(
                                request_info=response.request_info,
                                history=response.history,
                                status=response.status
                            )
            
            except Exception as e:
                # Mark proxy as failed if used
                if self.proxy_manager:
                    proxy = self.proxy_manager.get_current_proxy()
                    if proxy:
                        self.proxy_manager.mark_proxy_failed(proxy, str(e))
                        # Rotate to next proxy for retry
                        self.proxy_manager.rotate_proxy()
                
                if attempt == self.retry_attempts - 1:
                    logger.error(f"Failed to download {url} after {self.retry_attempts} attempts: {e}")
                    raise
                else:
                    logger.warning(f"Download attempt {attempt + 1} failed for {url}: {e}")
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
        
        return None, file_info
    
    def _is_valid_url(self, url: str) -> bool:
        """Validate URL format"""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except:
            return False
    
    def _generate_filename(self, url: str, movie_id: int, file_type: str, quality: str) -> str:
        """Generate safe filename for downloaded media"""
        
        # Extract original filename from URL
        parsed_url = urlparse(url)
        original_name = Path(unquote(parsed_url.path)).name
        
        # Get file extension
        extension = self._get_file_extension(url)
        
        # Generate timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Create safe filename
        safe_filename = f"movie_{movie_id}_{file_type}_{quality}_{timestamp}{extension}"
        
        return safe_filename
    
    def _get_file_extension(self, url: str, content_type: str = None) -> str:
        """Determine file extension from URL or content type"""
        
        # Try to get extension from URL
        parsed_url = urlparse(url)
        path_ext = Path(unquote(parsed_url.path)).suffix
        
        if path_ext:
            return path_ext.lower()
        
        # Try to get extension from content type
        if content_type:
            extension = mimetypes.guess_extension(content_type)
            if extension:
                return extension.lower()
        
        # Default extensions based on common patterns
        if "image" in url.lower() or (content_type and "image" in content_type):
            return ".jpg"
        elif "video" in url.lower() or (content_type and "video" in content_type):
            return ".mp4"
        else:
            return ".bin"  # Binary file as fallback
    
    async def _check_existing_file(self, filename: str, movie_id: int) -> Optional[Dict[str, Any]]:
        """Check if file already exists"""
        
        movie_dir = settings.DOWNLOADS_DIR / f"movie_{movie_id}"
        file_path = movie_dir / filename
        
        if file_path.exists():
            file_info = await self.storage_service.get_file_info(str(file_path))
            if file_info:
                return {
                    "local_path": str(file_path),
                    "filename": filename,
                    "file_size": file_info["file_size"],
                    "file_hash": file_info["file_hash"]
                }
        
        return None
    
    async def download_multiple_files(
        self,
        download_requests: List[Dict[str, Any]],
        max_concurrent: int = None
    ) -> List[Dict[str, Any]]:
        """Download multiple media files concurrently"""
        
        if max_concurrent is None:
            max_concurrent = self.concurrent_downloads
        
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def download_with_semaphore(request):
            async with semaphore:
                return await self.download_media_file(**request)
        
        # Create download tasks
        tasks = [download_with_semaphore(request) for request in download_requests]
        
        # Execute downloads
        logger.info(f"Starting download of {len(tasks)} files with max {max_concurrent} concurrent downloads")
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        download_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                download_results.append({
                    "success": False,
                    "error": str(result),
                    "request": download_requests[i]
                })
            else:
                download_results.append(result)
        
        # Log summary
        successful = sum(1 for r in download_results if r.get("success", False))
        failed = len(download_results) - successful
        total_size = sum(r.get("file_size", 0) for r in download_results if r.get("success", False))
        
        logger.info(f"Download batch completed: {successful} successful, {failed} failed, {total_size} bytes total")
        
        return download_results
    
    async def download_movie_media(
        self,
        movie_id: int,
        media_urls: Dict[str, List[str]],
        quality_preferences: Dict[str, str] = None
    ) -> Dict[str, Any]:
        """Download all media for a movie"""
        
        if quality_preferences is None:
            quality_preferences = {
                "poster": "high",
                "still": "medium", 
                "trailer": "high",
                "clip": "medium"
            }
        
        download_requests = []
        
        for file_type, urls in media_urls.items():
            quality = quality_preferences.get(file_type, "original")
            
            for url in urls:
                download_requests.append({
                    "url": url,
                    "movie_id": movie_id,
                    "file_type": file_type,
                    "quality": quality
                })
        
        results = await self.download_multiple_files(download_requests)
        
        # Organize results by file type
        organized_results = {}
        for result in results:
            file_type = result.get("file_type", "unknown")
            if file_type not in organized_results:
                organized_results[file_type] = []
            organized_results[file_type].append(result)
        
        # Calculate summary
        summary = {
            "movie_id": movie_id,
            "total_files": len(results),
            "successful_downloads": sum(1 for r in results if r.get("success", False)),
            "failed_downloads": sum(1 for r in results if not r.get("success", False)),
            "total_bytes": sum(r.get("file_size", 0) for r in results if r.get("success", False)),
            "results_by_type": organized_results
        }
        
        return summary
    
    def get_download_statistics(self) -> Dict[str, Any]:
        """Get download statistics"""
        
        success_rate = 0
        if self.download_stats["total_downloads"] > 0:
            success_rate = self.download_stats["successful_downloads"] / self.download_stats["total_downloads"]
        
        return {
            **self.download_stats,
            "success_rate": success_rate,
            "average_file_size": (
                self.download_stats["total_bytes"] / self.download_stats["successful_downloads"]
                if self.download_stats["successful_downloads"] > 0 else 0
            ),
            "concurrent_downloads": self.concurrent_downloads,
            "download_timeout": self.download_timeout,
            "max_file_size": self.max_file_size
        }
    
    def reset_statistics(self) -> None:
        """Reset download statistics"""
        
        self.download_stats = {
            "total_downloads": 0,
            "successful_downloads": 0,
            "failed_downloads": 0,
            "total_bytes": 0
        }
        
        logger.info("Download statistics reset")
    
    async def cleanup_failed_downloads(self) -> Dict[str, Any]:
        """Clean up failed or incomplete downloads"""
        
        cleanup_result = {
            "files_removed": 0,
            "space_freed": 0,
            "errors": []
        }
        
        downloads_dir = settings.DOWNLOADS_DIR
        
        try:
            for movie_dir in downloads_dir.iterdir():
                if movie_dir.is_dir() and movie_dir.name.startswith("movie_"):
                    for file_path in movie_dir.iterdir():
                        if file_path.is_file():
                            # Check for incomplete files (very small or corrupted)
                            file_size = file_path.stat().st_size
                            
                            if file_size < 1024:  # Less than 1KB, likely incomplete
                                try:
                                    file_path.unlink()
                                    cleanup_result["files_removed"] += 1
                                    cleanup_result["space_freed"] += file_size
                                except Exception as e:
                                    cleanup_result["errors"].append(f"Failed to remove {file_path}: {e}")
            
            logger.info(f"Cleanup completed: {cleanup_result['files_removed']} files removed, {cleanup_result['space_freed']} bytes freed")
            
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")
            cleanup_result["errors"].append(str(e))
        
        return cleanup_result
    
    def configure_download_settings(
        self,
        concurrent_downloads: int = None,
        download_timeout: int = None,
        max_file_size: int = None,
        retry_attempts: int = None
    ) -> Dict[str, Any]:
        """Configure download settings"""
        
        if concurrent_downloads is not None:
            self.concurrent_downloads = max(1, min(concurrent_downloads, 20))
        
        if download_timeout is not None:
            self.download_timeout = max(10, min(download_timeout, 300))
        
        if max_file_size is not None:
            self.max_file_size = max(1024 * 1024, min(max_file_size, 1024 * 1024 * 1024))  # 1MB to 1GB
        
        if retry_attempts is not None:
            self.retry_attempts = max(1, min(retry_attempts, 10))
        
        current_settings = {
            "concurrent_downloads": self.concurrent_downloads,
            "download_timeout": self.download_timeout,
            "max_file_size": self.max_file_size,
            "retry_attempts": self.retry_attempts
        }
        
        logger.info(f"Download settings updated: {current_settings}")
        
        return current_settings