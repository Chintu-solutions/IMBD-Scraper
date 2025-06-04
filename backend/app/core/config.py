"""
Enhanced IMDb Scraper - Configuration Management
===============================================

Centralized configuration management using Pydantic Settings.
Supports environment variables, .env files, and default values.

Usage:
    from app.core.config import settings
    
    # Access configuration
    db_url = settings.DATABASE_URL
    debug = settings.DEBUG
"""

import os
from typing import List, Optional, Any, Dict
from pathlib import Path
from pydantic import BaseSettings, validator, PostgresDsn, RedisDsn
from pydantic.networks import AnyHttpUrl


class Settings(BaseSettings):
    """Application settings with environment variable support"""
    
    # ==========================================
    # APPLICATION SETTINGS
    # ==========================================
    APP_NAME: str = "Enhanced IMDb Scraper"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"  # development, staging, production
    API_V1_STR: str = "/api/v1"
    
    # ==========================================
    # SECURITY SETTINGS
    # ==========================================
    SECRET_KEY: str = "super-secret-key-change-in-production-immediately"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Password requirements
    MIN_PASSWORD_LENGTH: int = 8
    REQUIRE_UPPERCASE: bool = True
    REQUIRE_LOWERCASE: bool = True
    REQUIRE_DIGITS: bool = True
    REQUIRE_SPECIAL_CHARS: bool = True
    
    # ==========================================
    # DATABASE SETTINGS
    # ==========================================
    DATABASE_URL: str = "postgresql+asyncpg://scraper_user:scraper_pass@localhost:5432/imdb_scraper"
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 30
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 3600
    DB_ECHO: bool = False
    
    @validator("DATABASE_URL", pre=True)
    def validate_database_url(cls, v):
        """Ensure database URL is properly formatted"""
        if not v:
            raise ValueError("DATABASE_URL is required")
        if not v.startswith(("postgresql://", "postgresql+asyncpg://")):
            if v.startswith("postgres://"):
                v = v.replace("postgres://", "postgresql://")
            elif not v.startswith("postgresql"):
                raise ValueError("DATABASE_URL must be a PostgreSQL URL")
        return v
    
    # ==========================================
    # REDIS SETTINGS
    # ==========================================
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_MAX_CONNECTIONS: int = 100
    REDIS_RETRY_ON_TIMEOUT: bool = True
    REDIS_SOCKET_KEEPALIVE: bool = True
    REDIS_SOCKET_KEEPALIVE_OPTIONS: Dict[str, int] = {}
    
    # Cache settings
    CACHE_DEFAULT_TTL: int = 3600  # 1 hour
    CACHE_LONG_TTL: int = 86400    # 24 hours
    CACHE_SHORT_TTL: int = 300     # 5 minutes
    
    @validator("REDIS_URL", pre=True)
    def validate_redis_url(cls, v):
        """Ensure Redis URL is properly formatted"""
        if not v:
            raise ValueError("REDIS_URL is required")
        if not v.startswith("redis://"):
            raise ValueError("REDIS_URL must start with redis://")
        return v
    
    # ==========================================
    # CORS SETTINGS
    # ==========================================
    ALLOWED_HOSTS: List[str] = ["*"]
    CORS_ORIGINS: List[AnyHttpUrl] = []
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: List[str] = ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"]
    CORS_ALLOW_HEADERS: List[str] = ["*"]
    
    @validator("CORS_ORIGINS", pre=True)
    def assemble_cors_origins(cls, v: Any) -> List[str]:
        """Parse CORS origins from string or list"""
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError("CORS_ORIGINS must be a list or comma-separated string")
    
    # ==========================================
    # LOGGING SETTINGS
    # ==========================================
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "structured"  # structured, simple, json
    LOG_FILE: Optional[str] = None
    LOG_MAX_SIZE: str = "100MB"
    LOG_BACKUP_COUNT: int = 5
    LOG_ROTATION: str = "daily"  # daily, weekly, size
    
    # Monitoring
    ENABLE_METRICS: bool = True
    METRICS_PORT: int = 9090
    ENABLE_TRACING: bool = False
    JAEGER_ENDPOINT: Optional[str] = None
    
    @validator("LOG_LEVEL")
    def validate_log_level(cls, v):
        """Ensure log level is valid"""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"LOG_LEVEL must be one of {valid_levels}")
        return v.upper()
    
    # ==========================================
    # SCRAPING SETTINGS
    # ==========================================
    # Rate limiting
    MAX_CONCURRENT_SCRAPES: int = 5
    DEFAULT_DELAY_MIN: float = 2.0
    DEFAULT_DELAY_MAX: float = 5.0
    MAX_RETRIES: int = 3
    RETRY_DELAY: float = 10.0
    
    # Browser settings
    BROWSER_TYPE: str = "chromium"  # chromium, firefox, webkit
    HEADLESS: bool = True
    BROWSER_TIMEOUT: int = 30000  # 30 seconds
    PAGE_LOAD_TIMEOUT: int = 60000  # 60 seconds
    
    # Proxy settings
    PROXY_HOST: Optional[str] = None
    PROXY_PORT: Optional[int] = None
    PROXY_USERNAME: Optional[str] = None
    PROXY_PASSWORD: Optional[str] = None
    PROXY_ROTATION_ENABLED: bool = False
    PROXY_POOL_SIZE: int = 10
    
    # Anti-detection
    USE_STEALTH: bool = True
    ROTATE_USER_AGENTS: bool = True
    SIMULATE_HUMAN_BEHAVIOR: bool = True
    RANDOM_VIEWPORT: bool = True
    
    @validator("MAX_CONCURRENT_SCRAPES")
    def validate_max_concurrent_scrapes(cls, v):
        """Ensure reasonable concurrency limits"""
        if v < 1:
            raise ValueError("MAX_CONCURRENT_SCRAPES must be at least 1")
        if v > 50:
            raise ValueError("MAX_CONCURRENT_SCRAPES should not exceed 50")
        return v
    
    # ==========================================
    # EXTERNAL API SETTINGS
    # ==========================================
    # ipstack for IP geolocation (proxy validation)
    IPSTACK_API_KEY: Optional[str] = None
    IPSTACK_TIMEOUT: int = 10
    IPSTACK_MAX_RETRIES: int = 3
    
    # Optional external services
    WEATHER_API_KEY: Optional[str] = None  # For filming locations
    NEWS_API_KEY: Optional[str] = None     # For movie news
    
    # ==========================================
    # STORAGE SETTINGS
    # ==========================================
    # Local storage
    DATA_DIR: Path = Path("data")
    DOWNLOADS_DIR: Path = DATA_DIR / "downloads"
    EXPORTS_DIR: Path = DATA_DIR / "exports"
    BACKUPS_DIR: Path = DATA_DIR / "backups"
    TEMP_DIR: Path = DATA_DIR / "temp"
    
    # MinIO settings (S3-compatible storage)
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin123"
    MINIO_BUCKET: str = "imdb-media"
    MINIO_SECURE: bool = False
    MINIO_REGION: str = "us-east-1"
    
    # File handling
    MAX_FILE_SIZE: int = 100 * 1024 * 1024  # 100MB
    ALLOWED_IMAGE_TYPES: List[str] = ["jpg", "jpeg", "png", "webp"]
    ALLOWED_VIDEO_TYPES: List[str] = ["mp4", "webm", "mov", "avi"]
    
    # ==========================================
    # BACKGROUND JOBS SETTINGS
    # ==========================================
    # Celery settings
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"
    CELERY_TASK_SERIALIZER: str = "json"
    CELERY_RESULT_SERIALIZER: str = "json"
    CELERY_ACCEPT_CONTENT: List[str] = ["json"]
    CELERY_TIMEZONE: str = "UTC"
    CELERY_ENABLE_UTC: bool = True
    
    # Task settings
    TASK_DEFAULT_QUEUE: str = "default"
    TASK_ROUTES: Dict[str, Dict[str, str]] = {
        "app.workers.scraper_tasks.*": {"queue": "scraping"},
        "app.workers.media_tasks.*": {"queue": "media"},
        "app.workers.cleanup_tasks.*": {"queue": "cleanup"},
    }
    
    # ==========================================
    # PERFORMANCE SETTINGS
    # ==========================================
    # API settings
    MAX_PAGE_SIZE: int = 1000
    DEFAULT_PAGE_SIZE: int = 50
    MAX_QUERY_COMPLEXITY: int = 100
    
    # Memory management
    MAX_MEMORY_USAGE: int = 2 * 1024 * 1024 * 1024  # 2GB
    GARBAGE_COLLECTION_THRESHOLD: int = 1000
    
    # ==========================================
    # DEVELOPMENT SETTINGS
    # ==========================================
    # Testing
    TESTING: bool = False
    TEST_DATABASE_URL: Optional[str] = None
    
    # Development tools
    ENABLE_DOCS: bool = True
    ENABLE_OPENAPI: bool = True
    DOCS_URL: str = "/docs"
    REDOC_URL: str = "/redoc"
    OPENAPI_URL: str = "/openapi.json"
    
    # ==========================================
    # VALIDATORS AND COMPUTED PROPERTIES
    # ==========================================
    
    @validator("DATA_DIR", "DOWNLOADS_DIR", "EXPORTS_DIR", "BACKUPS_DIR", "TEMP_DIR")
    def create_directories(cls, v):
        """Ensure required directories exist"""
        if isinstance(v, str):
            v = Path(v)
        v.mkdir(parents=True, exist_ok=True)
        return v
    
    @property
    def is_production(self) -> bool:
        """Check if running in production environment"""
        return self.ENVIRONMENT.lower() == "production"
    
    @property
    def is_development(self) -> bool:
        """Check if running in development environment"""
        return self.ENVIRONMENT.lower() == "development"
    
    @property
    def database_config(self) -> Dict[str, Any]:
        """Get database configuration for SQLAlchemy"""
        return {
            "url": self.DATABASE_URL,
            "pool_size": self.DB_POOL_SIZE,
            "max_overflow": self.DB_MAX_OVERFLOW,
            "pool_timeout": self.DB_POOL_TIMEOUT,
            "pool_recycle": self.DB_POOL_RECYCLE,
            "echo": self.DB_ECHO or self.DEBUG,
        }
    
    @property
    def redis_config(self) -> Dict[str, Any]:
        """Get Redis configuration"""
        return {
            "url": self.REDIS_URL,
            "max_connections": self.REDIS_MAX_CONNECTIONS,
            "retry_on_timeout": self.REDIS_RETRY_ON_TIMEOUT,
            "socket_keepalive": self.REDIS_SOCKET_KEEPALIVE,
            "socket_keepalive_options": self.REDIS_SOCKET_KEEPALIVE_OPTIONS,
        }
    
    @property
    def celery_config(self) -> Dict[str, Any]:
        """Get Celery configuration"""
        return {
            "broker_url": self.CELERY_BROKER_URL,
            "result_backend": self.CELERY_RESULT_BACKEND,
            "task_serializer": self.CELERY_TASK_SERIALIZER,
            "result_serializer": self.CELERY_RESULT_SERIALIZER,
            "accept_content": self.CELERY_ACCEPT_CONTENT,
            "timezone": self.CELERY_TIMEZONE,
            "enable_utc": self.CELERY_ENABLE_UTC,
            "task_routes": self.TASK_ROUTES,
        }
    
    def get_browser_config(self) -> Dict[str, Any]:
        """Get browser configuration for scraping"""
        config = {
            "headless": self.HEADLESS,
            "timeout": self.BROWSER_TIMEOUT,
        }
        
        if self.PROXY_HOST and self.PROXY_PORT:
            config["proxy"] = {
                "server": f"{self.PROXY_HOST}:{self.PROXY_PORT}",
            }
            if self.PROXY_USERNAME and self.PROXY_PASSWORD:
                config["proxy"].update({
                    "username": self.PROXY_USERNAME,
                    "password": self.PROXY_PASSWORD,
                })
        
        return config
    
    class Config:
        """Pydantic configuration"""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        
        # Allow extra fields for future extensibility
        extra = "allow"
        
        # Field validation
        validate_assignment = True
        use_enum_values = True


# ==========================================
# GLOBAL SETTINGS INSTANCE
# ==========================================

# Create global settings instance
settings = Settings()

# ==========================================
# CONFIGURATION UTILITIES
# ==========================================

def get_settings() -> Settings:
    """Get the current settings instance"""
    return settings


def reload_settings() -> Settings:
    """Reload settings from environment"""
    global settings
    settings = Settings()
    return settings


def validate_settings() -> List[str]:
    """Validate current settings and return any errors"""
    errors = []
    
    # Check required settings in production
    if settings.is_production:
        if settings.SECRET_KEY == "super-secret-key-change-in-production-immediately":
            errors.append("SECRET_KEY must be changed in production")
        
        if settings.DEBUG:
            errors.append("DEBUG should be False in production")
        
        if settings.ALLOWED_HOSTS == ["*"]:
            errors.append("ALLOWED_HOSTS should be restricted in production")
    
    # Check database connectivity requirements
    if not settings.DATABASE_URL:
        errors.append("DATABASE_URL is required")
    
    # Check Redis connectivity requirements  
    if not settings.REDIS_URL:
        errors.append("REDIS_URL is required")
    
    # Validate directories exist
    for dir_path in [settings.DATA_DIR, settings.DOWNLOADS_DIR, settings.EXPORTS_DIR]:
        if not dir_path.exists():
            errors.append(f"Directory does not exist: {dir_path}")
    
    return errors


def print_settings_summary():
    """Print a summary of current settings"""
    print(f"🎬 {settings.APP_NAME} v{settings.APP_VERSION}")
    print(f"Environment: {settings.ENVIRONMENT}")
    print(f"Debug Mode: {settings.DEBUG}")
    print(f"Log Level: {settings.LOG_LEVEL}")
    print(f"Database: {settings.DATABASE_URL.split('@')[-1] if '@' in settings.DATABASE_URL else 'Not configured'}")
    print(f"Redis: {settings.REDIS_URL.split('@')[-1] if '@' in settings.REDIS_URL else 'Not configured'}")
    print(f"Max Concurrent Scrapes: {settings.MAX_CONCURRENT_SCRAPES}")
    print(f"Proxy Enabled: {bool(settings.PROXY_HOST)}")


# ==========================================
# ENVIRONMENT-SPECIFIC CONFIGURATIONS
# ==========================================

def get_development_overrides() -> Dict[str, Any]:
    """Get development-specific setting overrides"""
    return {
        "DEBUG": True,
        "LOG_LEVEL": "DEBUG",
        "DB_ECHO": True,
        "ENABLE_DOCS": True,
        "CORS_ORIGINS": ["http://localhost:3000", "http://localhost:8501"],
    }


def get_production_overrides() -> Dict[str, Any]:
    """Get production-specific setting overrides"""
    return {
        "DEBUG": False,
        "LOG_LEVEL": "INFO",
        "DB_ECHO": False,
        "ENABLE_DOCS": False,
        "HEADLESS": True,
    }


def apply_environment_overrides():
    """Apply environment-specific overrides"""
    if settings.is_development:
        overrides = get_development_overrides()
    elif settings.is_production:
        overrides = get_production_overrides()
    else:
        return
    
    for key, value in overrides.items():
        if hasattr(settings, key):
            setattr(settings, key, value)


# Apply overrides on import
apply_environment_overrides()