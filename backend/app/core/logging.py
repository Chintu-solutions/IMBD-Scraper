"""
Enhanced IMDb Scraper - Logging Configuration
============================================

Structured logging system with multiple output formats, file rotation,
and integration with monitoring systems.

Usage:
    from app.core.logging import get_logger, setup_logging
    
    # Setup logging (call once at startup)
    setup_logging()
    
    # Get logger for module
    logger = get_logger(__name__)
    logger.info("Hello world")
"""

import os
import sys
import json
import logging
import logging.handlers
from datetime import datetime
from typing import Dict, Any, Optional, Union
from pathlib import Path
import traceback
from contextvars import ContextVar

import structlog
from structlog.stdlib import LoggerFactory, add_logger_name, add_log_level
from structlog.dev import ConsoleRenderer
from structlog.processors import TimeStamper, StackInfoRenderer, format_exc_info

from app.core.config import settings

# ==========================================
# CONTEXT VARIABLES FOR REQUEST TRACKING
# ==========================================

# Context variables for tracking request information
request_id_var: ContextVar[Optional[str]] = ContextVar('request_id', default=None)
user_id_var: ContextVar[Optional[str]] = ContextVar('user_id', default=None)
session_id_var: ContextVar[Optional[str]] = ContextVar('session_id', default=None)
job_id_var: ContextVar[Optional[str]] = ContextVar('job_id', default=None)


# ==========================================
# CUSTOM STRUCTLOG PROCESSORS
# ==========================================

def add_request_context(logger, method_name, event_dict):
    """Add request context to log entries"""
    request_id = request_id_var.get()
    user_id = user_id_var.get()
    session_id = session_id_var.get()
    job_id = job_id_var.get()
    
    if request_id:
        event_dict['request_id'] = request_id
    if user_id:
        event_dict['user_id'] = user_id
    if session_id:
        event_dict['session_id'] = session_id
    if job_id:
        event_dict['job_id'] = job_id
    
    return event_dict


def add_app_context(logger, method_name, event_dict):
    """Add application context to log entries"""
    event_dict.update({
        'app_name': settings.APP_NAME,
        'app_version': settings.APP_VERSION,
        'environment': settings.ENVIRONMENT,
    })
    return event_dict


def add_process_info(logger, method_name, event_dict):
    """Add process information to log entries"""
    event_dict.update({
        'process_id': os.getpid(),
        'thread_name': getattr(logging.current_thread(), 'name', 'unknown'),
    })
    return event_dict


def censor_sensitive_data(logger, method_name, event_dict):
    """Remove or mask sensitive information from logs"""
    sensitive_keys = {
        'password', 'token', 'secret', 'key', 'authorization',
        'cookie', 'session', 'csrf', 'api_key', 'access_token',
        'refresh_token', 'proxy_password', 'database_url'
    }
    
    def _censor_dict(obj, max_depth=5):
        if max_depth <= 0:
            return obj
        
        if isinstance(obj, dict):
            return {
                k: "***CENSORED***" if any(sens in k.lower() for sens in sensitive_keys)
                else _censor_dict(v, max_depth - 1)
                for k, v in obj.items()
            }
        elif isinstance(obj, (list, tuple)):
            return type(obj)(_censor_dict(item, max_depth - 1) for item in obj)
        else:
            return obj
    
    return _censor_dict(event_dict)


def add_exception_details(logger, method_name, event_dict):
    """Add detailed exception information to log entries"""
    if 'exception' in event_dict:
        exc = event_dict['exception']
        if isinstance(exc, Exception):
            event_dict.update({
                'exception_type': exc.__class__.__name__,
                'exception_module': exc.__class__.__module__,
                'exception_args': str(exc.args),
                'traceback': traceback.format_exc() if settings.DEBUG else None,
            })
    
    return event_dict


# ==========================================
# CUSTOM FORMATTERS
# ==========================================

class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging"""
    
    def format(self, record):
        log_entry = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_entry['exception'] = {
                'type': record.exc_info[0].__name__,
                'message': str(record.exc_info[1]),
                'traceback': self.formatException(record.exc_info) if settings.DEBUG else None,
            }
        
        # Add extra fields from record
        for key, value in record.__dict__.items():
            if key not in log_entry and not key.startswith('_'):
                log_entry[key] = value
        
        return json.dumps(log_entry, default=str, ensure_ascii=False)


class ColoredFormatter(logging.Formatter):
    """Colored formatter for console output"""
    
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
    }
    RESET = '\033[0m'
    
    def format(self, record):
        # Add color to level name
        level_color = self.COLORS.get(record.levelname, '')
        record.levelname = f"{level_color}{record.levelname}{self.RESET}"
        
        # Add color to logger name
        record.name = f"\033[34m{record.name}{self.RESET}"  # Blue
        
        return super().format(record)


# ==========================================
# FILE HANDLERS WITH ROTATION
# ==========================================

def create_file_handler(filename: str, max_size: str = "100MB", backup_count: int = 5) -> logging.Handler:
    """Create rotating file handler"""
    
    # Parse max_size
    size_multipliers = {'KB': 1024, 'MB': 1024**2, 'GB': 1024**3}
    size_str = max_size.upper()
    
    for suffix, multiplier in size_multipliers.items():
        if size_str.endswith(suffix):
            max_bytes = int(size_str[:-len(suffix)]) * multiplier
            break
    else:
        max_bytes = int(max_size)  # Assume bytes if no suffix
    
    # Create handler
    handler = logging.handlers.RotatingFileHandler(
        filename=filename,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8'
    )
    
    return handler


def create_timed_file_handler(filename: str, when: str = "midnight", backup_count: int = 7) -> logging.Handler:
    """Create time-based rotating file handler"""
    
    handler = logging.handlers.TimedRotatingFileHandler(
        filename=filename,
        when=when,
        backupCount=backup_count,
        encoding='utf-8'
    )
    
    # Add timestamp to rotated files
    handler.suffix = "%Y-%m-%d"
    
    return handler


# ==========================================
# LOGGING SETUP
# ==========================================

def setup_logging() -> None:
    """Setup structured logging with multiple outputs"""
    
    # Create logs directory if it doesn't exist
    if settings.LOG_FILE:
        log_path = Path(settings.LOG_FILE)
        log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Configure structlog processors
    processors = [
        add_request_context,
        add_app_context,
        add_process_info,
        censor_sensitive_data,
        add_exception_details,
        add_logger_name,
        add_log_level,
        TimeStamper(fmt="iso"),
        StackInfoRenderer(),
        format_exc_info,
    ]
    
    # Add format-specific processors
    if settings.LOG_FORMAT == "json":
        processors.append(structlog.processors.JSONRenderer())
    elif settings.LOG_FORMAT == "structured":
        if sys.stdout.isatty():
            # Colored console output for terminals
            processors.append(ConsoleRenderer(colors=True))
        else:
            # Plain console output for non-terminals
            processors.append(ConsoleRenderer(colors=False))
    else:  # simple format
        processors.append(structlog.dev.ConsoleRenderer(colors=False))
    
    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Configure standard library logging
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.LOG_LEVEL))
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    
    if settings.LOG_FORMAT == "json":
        console_handler.setFormatter(JSONFormatter())
    elif settings.LOG_FORMAT == "structured":
        if sys.stdout.isatty():
            console_handler.setFormatter(ColoredFormatter(
                '%(asctime)s | %(levelname)s | %(name)s | %(message)s'
            ))
        else:
            console_handler.setFormatter(logging.Formatter(
                '%(asctime)s | %(levelname)s | %(name)s | %(message)s'
            ))
    else:  # simple
        console_handler.setFormatter(logging.Formatter(
            '%(levelname)s: %(message)s'
        ))
    
    root_logger.addHandler(console_handler)
    
    # File handler (if configured)
    if settings.LOG_FILE:
        if settings.LOG_ROTATION == "size":
            file_handler = create_file_handler(
                settings.LOG_FILE,
                settings.LOG_MAX_SIZE,
                settings.LOG_BACKUP_COUNT
            )
        else:  # time-based rotation
            file_handler = create_timed_file_handler(
                settings.LOG_FILE,
                "midnight" if settings.LOG_ROTATION == "daily" else "W0",  # W0 = weekly
                settings.LOG_BACKUP_COUNT
            )
        
        # Always use JSON format for file logs
        file_handler.setFormatter(JSONFormatter())
        root_logger.addHandler(file_handler)
    
    # Set specific log levels for noisy libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("selenium").setLevel(logging.WARNING)
    logging.getLogger("playwright").setLevel(logging.WARNING)
    
    # SQLAlchemy logging
    if settings.DB_ECHO:
        logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)
    else:
        logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
    
    # Redis logging
    logging.getLogger("redis").setLevel(logging.WARNING)
    
    # Celery logging
    logging.getLogger("celery").setLevel(logging.INFO)
    
    print(f"✅ Logging configured: level={settings.LOG_LEVEL}, format={settings.LOG_FORMAT}")


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a logger instance for the given name"""
    return structlog.get_logger(name)


# ==========================================
# CONTEXT MANAGERS FOR REQUEST TRACKING
# ==========================================

class LogContext:
    """Context manager for adding contextual information to logs"""
    
    def __init__(self, **context):
        self.context = context
        self.tokens = []
    
    def __enter__(self):
        # Set context variables
        for key, value in self.context.items():
            if key == 'request_id':
                token = request_id_var.set(value)
            elif key == 'user_id':
                token = user_id_var.set(value)
            elif key == 'session_id':
                token = session_id_var.set(value)
            elif key == 'job_id':
                token = job_id_var.set(value)
            else:
                continue
            
            self.tokens.append((key, token))
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Reset context variables
        for key, token in self.tokens:
            if key == 'request_id':
                request_id_var.reset(token)
            elif key == 'user_id':
                user_id_var.reset(token)
            elif key == 'session_id':
                session_id_var.reset(token)
            elif key == 'job_id':
                job_id_var.reset(token)


def with_request_context(request_id: str, user_id: Optional[str] = None, session_id: Optional[str] = None):
    """Context manager for request logging"""
    context = {'request_id': request_id}
    if user_id:
        context['user_id'] = user_id
    if session_id:
        context['session_id'] = session_id
    
    return LogContext(**context)


def with_job_context(job_id: str, user_id: Optional[str] = None):
    """Context manager for background job logging"""
    context = {'job_id': job_id}
    if user_id:
        context['user_id'] = user_id
    
    return LogContext(**context)


# ==========================================
# PERFORMANCE LOGGING
# ==========================================

class PerformanceLogger:
    """Logger for tracking performance metrics"""
    
    def __init__(self, logger: structlog.stdlib.BoundLogger):
        self.logger = logger
    
    def log_duration(self, operation: str, duration: float, **extra):
        """Log operation duration"""
        self.logger.info(
            "Performance metric",
            operation=operation,
            duration_ms=round(duration * 1000, 2),
            **extra
        )
    
    def log_query_performance(self, query: str, duration: float, rows_affected: int = 0):
        """Log database query performance"""
        self.logger.info(
            "Database query performance",
            query_type=query.split()[0].upper() if query else "UNKNOWN",
            duration_ms=round(duration * 1000, 2),
            rows_affected=rows_affected,
            query_preview=query[:100] + "..." if len(query) > 100 else query
        )
    
    def log_scraping_performance(
        self, 
        url: str, 
        duration: float, 
        success: bool, 
        items_scraped: int = 0,
        **extra
    ):
        """Log scraping operation performance"""
        self.logger.info(
            "Scraping performance",
            url=url,
            duration_ms=round(duration * 1000, 2),
            success=success,
            items_scraped=items_scraped,
            **extra
        )


# ==========================================
# ERROR TRACKING AND ALERTING
# ==========================================

class ErrorTracker:
    """Track and categorize errors for monitoring"""
    
    def __init__(self, logger: structlog.stdlib.BoundLogger):
        self.logger = logger
    
    def log_error(
        self, 
        error: Exception, 
        context: Optional[Dict[str, Any]] = None,
        severity: str = "error",
        alert: bool = False
    ):
        """Log error with context and categorization"""
        
        error_info = {
            "error_type": error.__class__.__name__,
            "error_module": error.__class__.__module__,
            "error_message": str(error),
            "severity": severity,
            "alert_required": alert,
        }
        
        if context:
            error_info.update(context)
        
        # Add traceback in debug mode
        if settings.DEBUG:
            error_info["traceback"] = traceback.format_exc()
        
        self.logger.error("Application error", **error_info)
    
    def log_business_error(self, message: str, **context):
        """Log business logic errors"""
        self.logger.warning("Business logic error", message=message, **context)
    
    def log_external_service_error(self, service: str, error: Exception, **context):
        """Log external service errors"""
        self.log_error(
            error,
            context={
                "service": service,
                "error_category": "external_service",
                **context
            },
            alert=True
        )


# ==========================================
# MONITORING INTEGRATION
# ==========================================

def setup_monitoring_logging():
    """Setup logging for monitoring systems"""
    
    # Prometheus metrics logging
    if settings.ENABLE_METRICS:
        metrics_logger = get_logger("metrics")
        
        # Log application startup
        metrics_logger.info(
            "Application started",
            event="app_startup",
            version=settings.APP_VERSION,
            environment=settings.ENVIRONMENT
        )
    
    # Health check logging
    health_logger = get_logger("health")
    health_logger.info("Health monitoring initialized")


def log_system_metrics():
    """Log system metrics for monitoring"""
    import psutil
    
    metrics_logger = get_logger("metrics")
    
    try:
        # System metrics
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        metrics_logger.info(
            "System metrics",
            event="system_metrics",
            cpu_percent=cpu_percent,
            memory_percent=memory.percent,
            memory_available_mb=memory.available // (1024 * 1024),
            disk_percent=disk.percent,
            disk_free_gb=disk.free // (1024**3)
        )
        
    except Exception as e:
        metrics_logger.error("Failed to collect system metrics", error=str(e))


# ==========================================
# STRUCTURED LOGGING HELPERS
# ==========================================

def log_api_request(
    method: str,
    path: str, 
    status_code: int,
    duration: float,
    user_id: Optional[str] = None,
    request_size: Optional[int] = None,
    response_size: Optional[int] = None
):
    """Log API request with structured data"""
    
    api_logger = get_logger("api")
    
    log_data = {
        "event": "api_request",
        "method": method,
        "path": path,
        "status_code": status_code,
        "duration_ms": round(duration * 1000, 2),
    }
    
    if user_id:
        log_data["user_id"] = user_id
    if request_size:
        log_data["request_size_bytes"] = request_size
    if response_size:
        log_data["response_size_bytes"] = response_size
    
    # Determine log level based on status code
    if status_code >= 500:
        api_logger.error("API request failed", **log_data)
    elif status_code >= 400:
        api_logger.warning("API request error", **log_data)
    else:
        api_logger.info("API request completed", **log_data)


def log_database_operation(
    operation: str,
    table: str,
    duration: float,
    rows_affected: int = 0,
    query_id: Optional[str] = None
):
    """Log database operation with structured data"""
    
    db_logger = get_logger("database")
    
    db_logger.info(
        "Database operation",
        event="db_operation",
        operation=operation,
        table=table,
        duration_ms=round(duration * 1000, 2),
        rows_affected=rows_affected,
        query_id=query_id
    )


def log_scraping_operation(
    url: str,
    operation: str,
    duration: float,
    success: bool,
    items_found: int = 0,
    error: Optional[str] = None,
    proxy_used: Optional[str] = None
):
    """Log scraping operation with structured data"""
    
    scraping_logger = get_logger("scraping")
    
    log_data = {
        "event": "scraping_operation",
        "url": url,
        "operation": operation,
        "duration_ms": round(duration * 1000, 2),
        "success": success,
        "items_found": items_found,
    }
    
    if error:
        log_data["error"] = error
    if proxy_used:
        log_data["proxy_used"] = proxy_used
    
    if success:
        scraping_logger.info("Scraping operation completed", **log_data)
    else:
        scraping_logger.error("Scraping operation failed", **log_data)


def log_cache_operation(
    operation: str,
    key: str,
    hit: Optional[bool] = None,
    ttl: Optional[int] = None,
    size: Optional[int] = None
):
    """Log cache operation with structured data"""
    
    cache_logger = get_logger("cache")
    
    log_data = {
        "event": "cache_operation",
        "operation": operation,
        "key": key,
    }
    
    if hit is not None:
        log_data["cache_hit"] = hit
    if ttl:
        log_data["ttl_seconds"] = ttl
    if size:
        log_data["size_bytes"] = size
    
    cache_logger.debug("Cache operation", **log_data)


# ==========================================
# SECURITY LOGGING
# ==========================================

def log_security_event(
    event_type: str,
    user_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    severity: str = "info"
):
    """Log security-related events"""
    
    security_logger = get_logger("security")
    
    log_data = {
        "event": "security_event",
        "event_type": event_type,
        "severity": severity,
    }
    
    if user_id:
        log_data["user_id"] = user_id
    if ip_address:
        log_data["ip_address"] = ip_address
    if user_agent:
        log_data["user_agent"] = user_agent
    if details:
        log_data.update(details)
    
    if severity == "critical":
        security_logger.critical("Critical security event", **log_data)
    elif severity == "error":
        security_logger.error("Security error", **log_data)
    elif severity == "warning":
        security_logger.warning("Security warning", **log_data)
    else:
        security_logger.info("Security event", **log_data)


# ==========================================
# LOG ANALYSIS HELPERS
# ==========================================

def create_log_entry_id() -> str:
    """Create unique ID for log correlation"""
    import uuid
    return str(uuid.uuid4())


def log_correlation_start(operation: str, **context) -> str:
    """Start a correlated operation log"""
    correlation_id = create_log_entry_id()
    
    logger = get_logger("correlation")
    logger.info(
        "Operation started",
        event="operation_start",
        correlation_id=correlation_id,
        operation=operation,
        **context
    )
    
    return correlation_id


def log_correlation_end(
    correlation_id: str,
    operation: str,
    success: bool,
    duration: float,
    **context
):
    """End a correlated operation log"""
    
    logger = get_logger("correlation")
    
    log_data = {
        "event": "operation_end",
        "correlation_id": correlation_id,
        "operation": operation,
        "success": success,
        "duration_ms": round(duration * 1000, 2),
        **context
    }
    
    if success:
        logger.info("Operation completed successfully", **log_data)
    else:
        logger.error("Operation failed", **log_data)


# ==========================================
# DEBUGGING UTILITIES
# ==========================================

def debug_log_function_call(func):
    """Decorator to log function calls in debug mode"""
    
    if not settings.DEBUG:
        return func
    
    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        logger = get_logger(func.__module__)
        
        # Log function entry
        logger.debug(
            "Function called",
            function=func.__name__,
            args_count=len(args),
            kwargs_keys=list(kwargs.keys())
        )
        
        start_time = asyncio.get_event_loop().time()
        
        try:
            result = await func(*args, **kwargs)
            duration = asyncio.get_event_loop().time() - start_time
            
            # Log successful completion
            logger.debug(
                "Function completed",
                function=func.__name__,
                duration_ms=round(duration * 1000, 2),
                success=True
            )
            
            return result
            
        except Exception as e:
            duration = asyncio.get_event_loop().time() - start_time
            
            # Log error
            logger.debug(
                "Function failed",
                function=func.__name__,
                duration_ms=round(duration * 1000, 2),
                success=False,
                error=str(e)
            )
            
            raise
    
    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        logger = get_logger(func.__module__)
        
        # Log function entry
        logger.debug(
            "Function called",
            function=func.__name__,
            args_count=len(args),
            kwargs_keys=list(kwargs.keys())
        )
        
        import time
        start_time = time.time()
        
        try:
            result = func(*args, **kwargs)
            duration = time.time() - start_time
            
            # Log successful completion
            logger.debug(
                "Function completed",
                function=func.__name__,
                duration_ms=round(duration * 1000, 2),
                success=True
            )
            
            return result
            
        except Exception as e:
            duration = time.time() - start_time
            
            # Log error
            logger.debug(
                "Function failed",
                function=func.__name__,
                duration_ms=round(duration * 1000, 2),
                success=False,
                error=str(e)
            )
            
            raise
    
    # Return appropriate wrapper based on function type
    import asyncio
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    else:
        return sync_wrapper


# ==========================================
# LOG CONFIGURATION VALIDATION
# ==========================================

def validate_logging_config() -> List[str]:
    """Validate logging configuration"""
    errors = []
    
    # Check log level
    valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    if settings.LOG_LEVEL not in valid_levels:
        errors.append(f"Invalid LOG_LEVEL: {settings.LOG_LEVEL}")
    
    # Check log format
    valid_formats = ["simple", "structured", "json"]
    if settings.LOG_FORMAT not in valid_formats:
        errors.append(f"Invalid LOG_FORMAT: {settings.LOG_FORMAT}")
    
    # Check file path if specified
    if settings.LOG_FILE:
        log_path = Path(settings.LOG_FILE)
        if not log_path.parent.exists():
            try:
                log_path.parent.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                errors.append(f"Cannot create log directory: {e}")
    
    # Check rotation settings
    valid_rotations = ["daily", "weekly", "size"]
    if settings.LOG_ROTATION not in valid_rotations:
        errors.append(f"Invalid LOG_ROTATION: {settings.LOG_ROTATION}")
    
    return errors


# ==========================================
# INITIALIZATION AND CLEANUP
# ==========================================

def initialize_logging():
    """Initialize logging system with validation"""
    
    # Validate configuration
    config_errors = validate_logging_config()
    if config_errors:
        print(f"❌ Logging configuration errors:")
        for error in config_errors:
            print(f"  - {error}")
        sys.exit(1)
    
    # Setup logging
    setup_logging()
    
    # Setup monitoring integration
    setup_monitoring_logging()
    
    # Test logging
    logger = get_logger(__name__)
    logger.info(
        "Logging system initialized",
        log_level=settings.LOG_LEVEL,
        log_format=settings.LOG_FORMAT,
        log_file=settings.LOG_FILE,
        environment=settings.ENVIRONMENT
    )


def cleanup_logging():
    """Cleanup logging resources"""
    
    # Flush all handlers
    for handler in logging.root.handlers:
        handler.flush()
        handler.close()
    
    # Clear handlers
    logging.root.handlers.clear()
    
    logger = get_logger(__name__)
    logger.info("Logging system shutdown")


# ==========================================
# EXPORTS
# ==========================================

__all__ = [
    # Main functions
    "setup_logging",
    "get_logger",
    "initialize_logging",
    "cleanup_logging",
    
    # Context managers
    "LogContext",
    "with_request_context", 
    "with_job_context",
    
    # Specialized loggers
    "PerformanceLogger",
    "ErrorTracker",
    
    # Structured logging helpers
    "log_api_request",
    "log_database_operation",
    "log_scraping_operation",
    "log_cache_operation",
    "log_security_event",
    
    # Correlation logging
    "log_correlation_start",
    "log_correlation_end",
    "create_log_entry_id",
    
    # Debug utilities
    "debug_log_function_call",
    
    # Monitoring
    "setup_monitoring_logging",
    "log_system_metrics",
    
    # Validation
    "validate_logging_config",
    
    # Context variables
    "request_id_var",
    "user_id_var", 
    "session_id_var",
    "job_id_var",
]