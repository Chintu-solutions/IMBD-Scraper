"""
Enhanced IMDb Scraper - Database Management
==========================================

Async database connection management using SQLAlchemy 2.0+ with PostgreSQL.
Includes connection pooling, session management, and health checks.

Usage:
    from app.core.database import get_db, engine, Base
    
    # Dependency injection
    async def some_endpoint(db: AsyncSession = Depends(get_db)):
        # Use database session
        pass
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional, Dict, Any
from urllib.parse import urlparse

from sqlalchemy import event, text, create_engine
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    AsyncEngine,
    async_sessionmaker,
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.pool import NullPool, QueuePool
from sqlalchemy.exc import SQLAlchemyError, DisconnectionError
from sqlalchemy.engine import Engine

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# ==========================================
# DATABASE BASE AND ENGINE
# ==========================================

# Create declarative base for all models
Base = declarative_base()

# Global engine instance
engine: Optional[AsyncEngine] = None

# Global session factory
AsyncSessionLocal: Optional[async_sessionmaker[AsyncSession]] = None

# Sync engine for migrations and admin tasks
sync_engine: Optional[Engine] = None
SyncSessionLocal: Optional[sessionmaker[Session]] = None


# ==========================================
# ENGINE CREATION AND CONFIGURATION
# ==========================================

def create_database_engine() -> AsyncEngine:
    """Create and configure the async database engine"""
    
    logger.info("Creating database engine...")
    
    # Parse database URL for logging (without credentials)
    parsed_url = urlparse(settings.DATABASE_URL)
    safe_url = f"{parsed_url.scheme}://**:**@{parsed_url.hostname}:{parsed_url.port}{parsed_url.path}"
    logger.info(f"Connecting to database: {safe_url}")
    
    # Configure connection pool
    pool_class = QueuePool if not settings.TESTING else NullPool
    
    # Create engine with optimized settings
    engine_config = {
        "url": settings.DATABASE_URL,
        "echo": settings.DB_ECHO,
        "echo_pool": settings.DEBUG,
        "future": True,
        "pool_pre_ping": True,  # Verify connections before use
        "pool_recycle": settings.DB_POOL_RECYCLE,
        "connect_args": {
            "server_settings": {
                "application_name": f"{settings.APP_NAME}_v{settings.APP_VERSION}",
                "jit": "off",  # Disable JIT for better connection performance
            },
            "command_timeout": 60,
        },
    }
    
    # Add pool settings for non-test environments
    if not settings.TESTING:
        engine_config.update({
            "poolclass": pool_class,
            "pool_size": settings.DB_POOL_SIZE,
            "max_overflow": settings.DB_MAX_OVERFLOW,
            "pool_timeout": settings.DB_POOL_TIMEOUT,
        })
    else:
        engine_config["poolclass"] = NullPool
    
    try:
        engine = create_async_engine(**engine_config)
        logger.info("Database engine created successfully")
        return engine
    except Exception as e:
        logger.error(f"Failed to create database engine: {e}")
        raise


def create_sync_engine() -> Engine:
    """Create sync engine for migrations and admin tasks"""
    
    # Convert async URL to sync URL
    sync_url = settings.DATABASE_URL.replace("+asyncpg", "").replace("postgresql+asyncpg", "postgresql")
    
    engine_config = {
        "url": sync_url,
        "echo": settings.DB_ECHO,
        "future": True,
        "pool_pre_ping": True,
        "pool_recycle": settings.DB_POOL_RECYCLE,
    }
    
    if not settings.TESTING:
        engine_config.update({
            "pool_size": settings.DB_POOL_SIZE,
            "max_overflow": settings.DB_MAX_OVERFLOW,
            "pool_timeout": settings.DB_POOL_TIMEOUT,
        })
    
    try:
        sync_engine = create_engine(**engine_config)
        logger.info("Sync database engine created successfully")
        return sync_engine
    except Exception as e:
        logger.error(f"Failed to create sync database engine: {e}")
        raise


# ==========================================
# SESSION MANAGEMENT
# ==========================================

def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create async session factory"""
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )


def create_sync_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Create sync session factory"""
    return sessionmaker(
        engine,
        autoflush=False,
        autocommit=False,
    )


# ==========================================
# DEPENDENCY INJECTION
# ==========================================

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency to get database session.
    
    Usage:
        async def endpoint(db: AsyncSession = Depends(get_db)):
            # Use db session
            pass
    """
    if AsyncSessionLocal is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as e:
            logger.error(f"Database session error: {e}")
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager to get database session.
    
    Usage:
        async with get_db_session() as db:
            # Use db session
            pass
    """
    if AsyncSessionLocal is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as e:
            logger.error(f"Database session error: {e}")
            await session.rollback()
            raise


def get_sync_db() -> Session:
    """Get sync database session (for migrations/admin tasks)"""
    if SyncSessionLocal is None:
        raise RuntimeError("Sync database not initialized.")
    
    return SyncSessionLocal()


# ==========================================
# DATABASE INITIALIZATION
# ==========================================

async def init_database() -> None:
    """Initialize database engine and session factory"""
    global engine, AsyncSessionLocal, sync_engine, SyncSessionLocal
    
    logger.info("Initializing database...")
    
    try:
        # Create async engine and session factory
        engine = create_database_engine()
        AsyncSessionLocal = create_session_factory(engine)
        
        # Create sync engine for migrations
        sync_engine = create_sync_engine()
        SyncSessionLocal = create_sync_session_factory(sync_engine)
        
        # Test connection
        await test_database_connection()
        
        logger.info("Database initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


async def close_database() -> None:
    """Close database connections"""
    global engine, sync_engine
    
    logger.info("Closing database connections...")
    
    try:
        if engine:
            await engine.dispose()
            logger.info("Async database engine disposed")
        
        if sync_engine:
            sync_engine.dispose()
            logger.info("Sync database engine disposed")
            
    except Exception as e:
        logger.error(f"Error closing database connections: {e}")


# ==========================================
# DATABASE HEALTH AND MONITORING
# ==========================================

async def test_database_connection() -> bool:
    """Test database connection"""
    if not engine:
        raise RuntimeError("Database engine not initialized")
    
    try:
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT 1"))
            row = result.fetchone()
            if row and row[0] == 1:
                logger.info("Database connection test successful")
                return True
            else:
                logger.error("Database connection test failed: unexpected result")
                return False
                
    except Exception as e:
        logger.error(f"Database connection test failed: {e}")
        raise


async def get_database_info() -> Dict[str, Any]:
    """Get database information and statistics"""
    if not engine:
        raise RuntimeError("Database engine not initialized")
    
    try:
        async with engine.begin() as conn:
            # Get database version
            version_result = await conn.execute(text("SELECT version()"))
            version = version_result.scalar()
            
            # Get database name
            db_name_result = await conn.execute(text("SELECT current_database()"))
            db_name = db_name_result.scalar()
            
            # Get connection info
            pool = engine.pool
            pool_info = {
                "size": pool.size(),
                "checked_in": pool.checkedin(),
                "checked_out": pool.checkedout(),
                "overflow": pool.overflow(),
                "invalid": pool.invalid(),
            } if hasattr(pool, 'size') else {}
            
            return {
                "database_name": db_name,
                "database_version": version,
                "pool_info": pool_info,
                "engine_info": {
                    "url": str(engine.url).replace(str(engine.url.password), "***") if engine.url.password else str(engine.url),
                    "echo": engine.echo,
                    "pool_timeout": getattr(engine.pool, 'timeout', None),
                    "pool_recycle": getattr(engine.pool, 'recycle', None),
                },
                "is_connected": True,
            }
            
    except Exception as e:
        logger.error(f"Failed to get database info: {e}")
        return {
            "is_connected": False,
            "error": str(e),
        }


async def check_database_health() -> Dict[str, Any]:
    """Comprehensive database health check"""
    health_status = {
        "status": "healthy",
        "checks": {},
        "timestamp": asyncio.get_event_loop().time(),
    }
    
    if not engine:
        health_status["status"] = "unhealthy"
        health_status["error"] = "Database engine not initialized"
        return health_status
    
    # Test basic connectivity
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        health_status["checks"]["connectivity"] = "pass"
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["checks"]["connectivity"] = f"fail: {e}"
    
    # Check pool health
    try:
        pool = engine.pool
        if hasattr(pool, 'size'):
            pool_ratio = pool.checkedout() / (pool.size() + pool.overflow())
            if pool_ratio > 0.9:
                health_status["checks"]["pool"] = f"warning: high usage ({pool_ratio:.1%})"
            else:
                health_status["checks"]["pool"] = "pass"
        else:
            health_status["checks"]["pool"] = "pass"
    except Exception as e:
        health_status["checks"]["pool"] = f"fail: {e}"
    
    # Test write capability
    try:
        async with engine.begin() as conn:
            await conn.execute(text("CREATE TEMP TABLE health_check (id INTEGER)"))
            await conn.execute(text("INSERT INTO health_check VALUES (1)"))
            result = await conn.execute(text("SELECT COUNT(*) FROM health_check"))
            count = result.scalar()
            if count == 1:
                health_status["checks"]["write"] = "pass"
            else:
                health_status["checks"]["write"] = "fail: unexpected count"
    except Exception as e:
        health_status["checks"]["write"] = f"fail: {e}"
    
    return health_status


# ==========================================
# DATABASE UTILITIES
# ==========================================

async def execute_raw_sql(sql: str, params: Optional[Dict[str, Any]] = None) -> Any:
    """Execute raw SQL query safely"""
    if not engine:
        raise RuntimeError("Database engine not initialized")
    
    try:
        async with engine.begin() as conn:
            result = await conn.execute(text(sql), params or {})
            return result
    except Exception as e:
        logger.error(f"Failed to execute raw SQL: {e}")
        raise


async def get_table_info(table_name: str) -> Dict[str, Any]:
    """Get information about a specific table"""
    sql = """
    SELECT 
        column_name,
        data_type,
        is_nullable,
        column_default,
        character_maximum_length
    FROM information_schema.columns 
    WHERE table_name = :table_name
    ORDER BY ordinal_position
    """
    
    try:
        result = await execute_raw_sql(sql, {"table_name": table_name})
        columns = []
        for row in result:
            columns.append({
                "name": row[0],
                "type": row[1],
                "nullable": row[2] == "YES",
                "default": row[3],
                "max_length": row[4],
            })
        
        return {
            "table_name": table_name,
            "columns": columns,
            "column_count": len(columns),
        }
        
    except Exception as e:
        logger.error(f"Failed to get table info for {table_name}: {e}")
        raise


async def get_database_statistics() -> Dict[str, Any]:
    """Get comprehensive database statistics"""
    stats = {}
    
    try:
        # Get database size
        size_sql = "SELECT pg_size_pretty(pg_database_size(current_database()))"
        result = await execute_raw_sql(size_sql)
        stats["database_size"] = result.scalar()
        
        # Get table statistics
        tables_sql = """
        SELECT 
            schemaname,
            tablename,
            n_tup_ins as inserts,
            n_tup_upd as updates,
            n_tup_del as deletes,
            n_live_tup as live_rows,
            n_dead_tup as dead_rows
        FROM pg_stat_user_tables
        ORDER BY n_live_tup DESC
        """
        result = await execute_raw_sql(tables_sql)
        tables = []
        for row in result:
            tables.append({
                "schema": row[0],
                "name": row[1],
                "inserts": row[2],
                "updates": row[3],
                "deletes": row[4],
                "live_rows": row[5],
                "dead_rows": row[6],
            })
        stats["tables"] = tables
        
        # Get connection statistics
        connections_sql = """
        SELECT 
            count(*) as total_connections,
            count(*) FILTER (WHERE state = 'active') as active_connections,
            count(*) FILTER (WHERE state = 'idle') as idle_connections
        FROM pg_stat_activity 
        WHERE datname = current_database()
        """
        result = await execute_raw_sql(connections_sql)
        row = result.fetchone()
        stats["connections"] = {
            "total": row[0],
            "active": row[1],
            "idle": row[2],
        }
        
    except Exception as e:
        logger.error(f"Failed to get database statistics: {e}")
        stats["error"] = str(e)
    
    return stats


# ==========================================
# TRANSACTION MANAGEMENT
# ==========================================

@asynccontextmanager
async def database_transaction() -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager for database transactions with automatic rollback on error.
    
    Usage:
        async with database_transaction() as db:
            # All operations are in a transaction
            # Automatic commit on success, rollback on error
            pass
    """
    if AsyncSessionLocal is None:
        raise RuntimeError("Database not initialized")
    
    async with AsyncSessionLocal() as session:
        async with session.begin():
            try:
                yield session
            except Exception as e:
                logger.error(f"Transaction error: {e}")
                await session.rollback()
                raise


class DatabaseManager:
    """Database manager class for advanced operations"""
    
    def __init__(self):
        self.engine = engine
        self.session_factory = AsyncSessionLocal
    
    async def create_tables(self):
        """Create all tables defined in models"""
        if not self.engine:
            raise RuntimeError("Database engine not initialized")
        
        logger.info("Creating database tables...")
        try:
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error(f"Failed to create database tables: {e}")
            raise
    
    async def drop_tables(self):
        """Drop all tables (WARNING: This will delete all data!)"""
        if not self.engine:
            raise RuntimeError("Database engine not initialized")
        
        logger.warning("Dropping all database tables...")
        try:
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.drop_all)
            logger.info("Database tables dropped successfully")
        except Exception as e:
            logger.error(f"Failed to drop database tables: {e}")
            raise
    
    async def truncate_tables(self, table_names: list[str]):
        """Truncate specific tables"""
        if not table_names:
            return
        
        logger.info(f"Truncating tables: {table_names}")
        try:
            async with self.engine.begin() as conn:
                for table_name in table_names:
                    await conn.execute(text(f"TRUNCATE TABLE {table_name} CASCADE"))
            logger.info("Tables truncated successfully")
        except Exception as e:
            logger.error(f"Failed to truncate tables: {e}")
            raise
    
    async def backup_database(self, backup_path: str):
        """Create database backup (requires pg_dump)"""
        import subprocess
        import tempfile
        
        logger.info(f"Creating database backup: {backup_path}")
        
        # Parse database URL
        parsed_url = urlparse(settings.DATABASE_URL.replace("+asyncpg", ""))
        
        # Prepare pg_dump command
        cmd = [
            "pg_dump",
            f"--host={parsed_url.hostname}",
            f"--port={parsed_url.port or 5432}",
            f"--username={parsed_url.username}",
            f"--dbname={parsed_url.path.lstrip('/')}",
            "--no-password",
            "--verbose",
            "--format=custom",
            f"--file={backup_path}",
        ]
        
        # Set password via environment
        env = {"PGPASSWORD": parsed_url.password} if parsed_url.password else {}
        
        try:
            result = subprocess.run(cmd, env=env, capture_output=True, text=True)
            if result.returncode == 0:
                logger.info("Database backup created successfully")
            else:
                logger.error(f"Database backup failed: {result.stderr}")
                raise RuntimeError(f"Backup failed: {result.stderr}")
        except Exception as e:
            logger.error(f"Failed to create database backup: {e}")
            raise


# ==========================================
# EVENT LISTENERS
# ==========================================

def setup_database_events():
    """Setup database event listeners for monitoring and debugging"""
    
    @event.listens_for(Engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        """Set database-specific settings on connection"""
        if "postgresql" in str(dbapi_connection):
            # PostgreSQL-specific settings
            cursor = dbapi_connection.cursor()
            cursor.execute("SET timezone TO 'UTC'")
            cursor.execute("SET statement_timeout = '300s'")
            cursor.close()
    
    @event.listens_for(Engine, "before_cursor_execute")
    def receive_before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        """Log slow queries in debug mode"""
        if settings.DEBUG and settings.LOG_LEVEL == "DEBUG":
            context._query_start_time = asyncio.get_event_loop().time()
    
    @event.listens_for(Engine, "after_cursor_execute")
    def receive_after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        """Log query execution time"""
        if settings.DEBUG and settings.LOG_LEVEL == "DEBUG":
            if hasattr(context, '_query_start_time'):
                total = asyncio.get_event_loop().time() - context._query_start_time
                if total > 1.0:  # Log queries taking more than 1 second
                    logger.warning(f"Slow query ({total:.3f}s): {statement[:100]}...")


# ==========================================
# INITIALIZATION
# ==========================================

# Setup event listeners
setup_database_events()

# Create database manager instance
db_manager = DatabaseManager()


# ==========================================
# EXPORTS
# ==========================================

__all__ = [
    "Base",
    "engine", 
    "AsyncSessionLocal",
    "sync_engine",
    "SyncSessionLocal",
    "get_db",
    "get_db_session",
    "get_sync_db",
    "database_transaction",
    "init_database",
    "close_database",
    "test_database_connection",
    "get_database_info",
    "check_database_health",
    "get_database_statistics",
    "execute_raw_sql",
    "get_table_info",
    "db_manager",
    "DatabaseManager",
]