"""
Enhanced IMDb Scraper - Core Module
====================================

This module contains the core functionality and shared components
for the Enhanced IMDb Scraper application.

Components:
- config: Application configuration management
- database: Database connection and session management
- cache: Redis caching functionality
- logging: Structured logging setup
- security: Authentication and security utilities

Usage:
    from app.core import settings, get_db, logger, cache
"""

from .config import settings
from .database import get_db, engine, Base, AsyncSessionLocal
from .logging import get_logger, setup_logging
from .cache import cache_manager, redis_client
from .security import create_access_token, verify_token, get_password_hash

__all__ = [
    # Configuration
    "settings",
    
    # Database
    "get_db",
    "engine", 
    "Base",
    "AsyncSessionLocal",
    
    # Logging
    "get_logger",
    "setup_logging",
    
    # Cache
    "cache_manager",
    "redis_client",
    
    # Security
    "create_access_token",
    "verify_token", 
    "get_password_hash",
]

# Version info
__version__ = "2.0.0"
__author__ = "Enhanced IMDb Scraper Team"
__email__ = "contact@imdb-scraper.com"

# Core module metadata
CORE_MODULES = {
    "config": "Application configuration and settings",
    "database": "Database connections and ORM setup", 
    "cache": "Redis caching and session management",
    "logging": "Structured logging and monitoring",
    "security": "Authentication and security utilities"
}

def get_core_info():
    """Get information about core modules"""
    return {
        "version": __version__,
        "modules": CORE_MODULES,
        "database_url": settings.DATABASE_URL.split("@")[-1] if "@" in settings.DATABASE_URL else "Not configured",
        "redis_url": settings.REDIS_URL.split("@")[-1] if "@" in settings.REDIS_URL else "Not configured",
        "debug_mode": settings.DEBUG,
        "log_level": settings.LOG_LEVEL
    }