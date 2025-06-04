"""
Storage Service - File storage and media management
"""

import os
import asyncio
import aiofiles
from pathlib import Path
from typing import Optional, Dict, Any, List, BinaryIO
from datetime import datetime
import hashlib
import mimetypes

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

class StorageService:
    """File storage and media management service"""
    
    def __init__(self):
        self.downloads_dir = settings.DOWNLOADS_DIR
        self.exports_dir = settings.EXPORTS_DIR
        self.temp_dir = settings.TEMP_DIR
        
        # Ensure directories exist
        self._ensure_directories()
    
    def _ensure_directories(self):
        """Ensure required directories exist"""
        for directory in [self.downloads_dir, self.exports_dir, self.temp_dir]:
            directory.mkdir(parents=True, exist_ok=True)
    
    def _generate_safe_filename(self, original_filename: str, prefix: str = "") -> str:
        """Generate safe filename with timestamp"""
        # Remove unsafe characters
        safe_name = "".join(c for c in original_filename if c.isalnum() or c in "._-")
        
        # Add timestamp to prevent collisions
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        name, ext = os.path.splitext(safe_name)
        
        if prefix:
            return f"{prefix}_{timestamp}_{name}{ext}"
        return f"{timestamp}_{name}{ext}"
    
    def _get_file_hash(self, file_path: Path) -> str:
        """Calculate MD5 hash of file"""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    
    async def save_downloaded_media(
        self, 
        file_data: bytes, 
        original_url: str,
        movie_id: int,
        file_type: str,
        file_extension: str = None
    ) -> Dict[str, Any]:
        """Save downloaded media file"""
        
        try:
            # Determine file extension
            if not file_extension:
                # Try to guess from URL or content type
                _, ext = os.path.splitext(original_url)
                file_extension = ext or ".jpg"
            
            # Generate safe filename
            base_name = f"movie_{movie_id}_{file_type}"
            filename = self._generate_safe_filename(f"{base_name}{file_extension}")
            
            # Create subdirectory for movie
            movie_dir = self.downloads_dir / f"movie_{movie_id}"
            movie_dir.mkdir(exist_ok=True)
            
            file_path = movie_dir / filename
            
            # Save file
            async with aiofiles.open(file_path, 'wb') as f:
                await f.write(file_data)
            
            # Calculate file info
            file_size = len(file_data)
            file_hash = hashlib.md5(file_data).hexdigest()
            
            logger.info(f"Saved media file: {file_path} ({file_size} bytes)")
            
            return {
                "success": True,
                "local_path": str(file_path),
                "filename": filename,
                "file_size": file_size,
                "file_hash": file_hash,
                "mime_type": mimetypes.guess_type(filename)[0]
            }
            
        except Exception as e:
            logger.error(f"Failed to save media file: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def save_exported_data(
        self, 
        data: Any, 
        filename: str,
        format: str = "json"
    ) -> Dict[str, Any]:
        """Save exported data to file"""
        
        try:
            # Generate safe filename
            safe_filename = self._generate_safe_filename(f"{filename}.{format}")
            file_path = self.exports_dir / safe_filename
            
            if format == "json":
                import json
                async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
                    await f.write(json.dumps(data, indent=2, default=str))
            
            elif format == "csv":
                import pandas as pd
                # Convert data to DataFrame and save
                if isinstance(data, list) and data:
                    df = pd.DataFrame(data)
                    df.to_csv(file_path, index=False)
                else:
                    raise ValueError("CSV export requires list of dictionaries")
            
            elif format == "txt":
                async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
                    await f.write(str(data))
            
            else:
                raise ValueError(f"Unsupported export format: {format}")
            
            file_size = file_path.stat().st_size
            
            logger.info(f"Exported data to: {file_path} ({file_size} bytes)")
            
            return {
                "success": True,
                "file_path": str(file_path),
                "filename": safe_filename,
                "file_size": file_size,
                "format": format
            }
            
        except Exception as e:
            logger.error(f"Failed to export data: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def save_temp_file(
        self, 
        file_data: bytes, 
        filename: str,
        ttl_hours: int = 24
    ) -> Dict[str, Any]:
        """Save temporary file with TTL"""
        
        try:
            # Generate safe filename
            safe_filename = self._generate_safe_filename(filename)
            file_path = self.temp_dir / safe_filename
            
            # Save file
            async with aiofiles.open(file_path, 'wb') as f:
                await f.write(file_data)
            
            file_size = len(file_data)
            
            # Schedule cleanup (in real implementation, use background task)
            # asyncio.create_task(self._cleanup_temp_file(file_path, ttl_hours))
            
            logger.info(f"Saved temp file: {file_path} ({file_size} bytes)")
            
            return {
                "success": True,
                "file_path": str(file_path),
                "filename": safe_filename,
                "file_size": file_size,
                "expires_in_hours": ttl_hours
            }
            
        except Exception as e:
            logger.error(f"Failed to save temp file: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_file_info(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Get information about a file"""
        
        try:
            path = Path(file_path)
            
            if not path.exists():
                return None
            
            stat = path.stat()
            
            return {
                "filename": path.name,
                "file_size": stat.st_size,
                "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "mime_type": mimetypes.guess_type(str(path))[0],
                "file_hash": self._get_file_hash(path),
                "exists": True
            }
            
        except Exception as e:
            logger.error(f"Failed to get file info: {e}")
            return None
    
    async def delete_file(self, file_path: str) -> bool:
        """Delete a file"""
        
        try:
            path = Path(file_path)
            
            if path.exists():
                path.unlink()
                logger.info(f"Deleted file: {file_path}")
                return True
            else:
                logger.warning(f"File not found: {file_path}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to delete file: {e}")
            return False
    
    async def move_file(self, source_path: str, destination_path: str) -> bool:
        """Move file from source to destination"""
        
        try:
            source = Path(source_path)
            destination = Path(destination_path)
            
            if not source.exists():
                logger.error(f"Source file not found: {source_path}")
                return False
            
            # Ensure destination directory exists
            destination.parent.mkdir(parents=True, exist_ok=True)
            
            source.rename(destination)
            logger.info(f"Moved file: {source_path} -> {destination_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to move file: {e}")
            return False
    
    async def copy_file(self, source_path: str, destination_path: str) -> bool:
        """Copy file from source to destination"""
        
        try:
            source = Path(source_path)
            destination = Path(destination_path)
            
            if not source.exists():
                logger.error(f"Source file not found: {source_path}")
                return False
            
            # Ensure destination directory exists
            destination.parent.mkdir(parents=True, exist_ok=True)
            
            # Copy file content
            async with aiofiles.open(source, 'rb') as src:
                async with aiofiles.open(destination, 'wb') as dst:
                    while chunk := await src.read(8192):
                        await dst.write(chunk)
            
            logger.info(f"Copied file: {source_path} -> {destination_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to copy file: {e}")
            return False
    
    async def list_directory_files(
        self, 
        directory_path: str,
        file_extension: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List files in directory"""
        
        try:
            directory = Path(directory_path)
            
            if not directory.exists() or not directory.is_dir():
                return []
            
            files = []
            
            for file_path in directory.iterdir():
                if file_path.is_file():
                    # Filter by extension if specified
                    if file_extension and not file_path.suffix.lower() == file_extension.lower():
                        continue
                    
                    file_info = await self.get_file_info(str(file_path))
                    if file_info:
                        file_info["full_path"] = str(file_path)
                        files.append(file_info)
            
            return sorted(files, key=lambda x: x["modified_at"], reverse=True)
            
        except Exception as e:
            logger.error(f"Failed to list directory files: {e}")
            return []
    
    async def get_storage_statistics(self) -> Dict[str, Any]:
        """Get storage usage statistics"""
        
        try:
            stats = {}
            
            for name, directory in [
                ("downloads", self.downloads_dir),
                ("exports", self.exports_dir),
                ("temp", self.temp_dir)
            ]:
                if directory.exists():
                    total_size = 0
                    file_count = 0
                    
                    for file_path in directory.rglob("*"):
                        if file_path.is_file():
                            total_size += file_path.stat().st_size
                            file_count += 1
                    
                    stats[name] = {
                        "total_size_bytes": total_size,
                        "total_size_mb": round(total_size / (1024 * 1024), 2),
                        "file_count": file_count,
                        "directory": str(directory)
                    }
                else:
                    stats[name] = {
                        "total_size_bytes": 0,
                        "total_size_mb": 0,
                        "file_count": 0,
                        "directory": str(directory)
                    }
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get storage statistics: {e}")
            return {}
    
    async def cleanup_old_files(
        self, 
        directory_path: str,
        max_age_days: int = 30
    ) -> Dict[str, Any]:
        """Clean up old files in directory"""
        
        try:
            directory = Path(directory_path)
            
            if not directory.exists():
                return {"deleted_count": 0, "freed_space_bytes": 0}
            
            cutoff_time = datetime.now().timestamp() - (max_age_days * 24 * 3600)
            
            deleted_count = 0
            freed_space = 0
            
            for file_path in directory.rglob("*"):
                if file_path.is_file():
                    file_stat = file_path.stat()
                    
                    if file_stat.st_mtime < cutoff_time:
                        file_size = file_stat.st_size
                        
                        try:
                            file_path.unlink()
                            deleted_count += 1
                            freed_space += file_size
                            logger.debug(f"Deleted old file: {file_path}")
                        except Exception as e:
                            logger.warning(f"Failed to delete old file {file_path}: {e}")
            
            logger.info(f"Cleanup completed: {deleted_count} files deleted, {freed_space} bytes freed")
            
            return {
                "deleted_count": deleted_count,
                "freed_space_bytes": freed_space,
                "freed_space_mb": round(freed_space / (1024 * 1024), 2)
            }
            
        except Exception as e:
            logger.error(f"Failed to cleanup old files: {e}")
            return {"deleted_count": 0, "freed_space_bytes": 0}
    
    async def create_backup(self, source_directory: str, backup_name: str) -> Dict[str, Any]:
        """Create backup of directory"""
        
        try:
            import zipfile
            from datetime import datetime
            
            source = Path(source_directory)
            
            if not source.exists():
                return {"success": False, "error": "Source directory not found"}
            
            # Create backup filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"{backup_name}_{timestamp}.zip"
            backup_path = self.exports_dir / backup_filename
            
            # Create zip archive
            with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for file_path in source.rglob("*"):
                    if file_path.is_file():
                        # Add file to zip with relative path
                        arcname = file_path.relative_to(source)
                        zipf.write(file_path, arcname)
            
            backup_size = backup_path.stat().st_size
            
            logger.info(f"Created backup: {backup_path} ({backup_size} bytes)")
            
            return {
                "success": True,
                "backup_path": str(backup_path),
                "backup_filename": backup_filename,
                "backup_size_bytes": backup_size,
                "backup_size_mb": round(backup_size / (1024 * 1024), 2)
            }
            
        except Exception as e:
            logger.error(f"Failed to create backup: {e}")
            return {"success": False, "error": str(e)}