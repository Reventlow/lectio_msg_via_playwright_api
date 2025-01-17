# logs.py

import psycopg
from psycopg_pool import AsyncConnectionPool
from datetime import datetime
from enum import Enum
from .import_env import get_env_variable
import asyncio

class LogLevel(str, Enum):
    SUCCESS = "SUCCESS"
    INFO = "INFO"
    WARNING = "WARNING"  # New Warning Level
    ERROR = "ERROR"

# Global variables for connection pools
_fastapi_connection_pool = None
_celery_connection_pool = None

async def init_connection_pool(pool_type: str = "fastapi"):
    """
    Initializes the asynchronous connection pool based on the pool type.
    """
    global _fastapi_connection_pool, _celery_connection_pool

    if pool_type == "fastapi":
        if _fastapi_connection_pool is None:
            conninfo = construct_conninfo()
            _fastapi_connection_pool = AsyncConnectionPool(
                min_size=1,
                max_size=10,
                conninfo=conninfo
            )
    elif pool_type == "celery":
        if _celery_connection_pool is None:
            conninfo = construct_conninfo()
            _celery_connection_pool = AsyncConnectionPool(
                min_size=1,
                max_size=10,
                conninfo=conninfo
            )
    else:
        raise ValueError("Unsupported pool_type. Choose 'fastapi' or 'celery'.")

def construct_conninfo() -> str:
    """
    Constructs the PostgreSQL connection string from environment variables.
    """
    POSTGRES_HOST = get_env_variable("POSTGRES_HOST", default_value="db")
    POSTGRES_DB = get_env_variable("POSTGRES_DB", default_value="logsdb")
    POSTGRES_USER = get_env_variable("POSTGRES_USER", default_value="myuser")
    POSTGRES_PASSWORD = get_env_variable("POSTGRES_PASSWORD", default_value="mypass")
    POSTGRES_PORT = get_env_variable("POSTGRES_PORT", default_value="5432")  # Default PostgreSQL port

    return f"host={POSTGRES_HOST} port={POSTGRES_PORT} dbname={POSTGRES_DB} user={POSTGRES_USER} password={POSTGRES_PASSWORD}"

async def get_connection(pool_type: str = "fastapi") -> AsyncConnectionPool:
    """
    Retrieves the connection pool based on the pool type.
    """
    if pool_type == "fastapi":
        if _fastapi_connection_pool is None:
            await init_connection_pool("fastapi")
        return _fastapi_connection_pool
    elif pool_type == "celery":
        if _celery_connection_pool is None:
            await init_connection_pool("celery")
        return _celery_connection_pool
    else:
        raise ValueError("Unsupported pool_type. Choose 'fastapi' or 'celery'.")

async def init_logs_table(pool_type: str = "fastapi"):
    """
    Creates the logs table if it doesn't exist.
    """
    pool = await get_connection(pool_type)
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS logs (
                    id SERIAL PRIMARY KEY,
                    timestamp TIMESTAMP NOT NULL,
                    log_level VARCHAR(20) NOT NULL,
                    task_id VARCHAR(255),
                    receiver VARCHAR(255),
                    description TEXT
                );
            """)
            await conn.commit()

async def log_event(timestamp: datetime, level: LogLevel, task_id: str, receiver: str, description: str, pool_type: str = "fastapi"):
    """
    Writes a log entry to the PostgreSQL database asynchronously.
    """
    pool = await get_connection(pool_type)
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                INSERT INTO logs (timestamp, log_level, task_id, receiver, description)
                VALUES (%s, %s, %s, %s, %s)
            """, (timestamp, level.value, task_id, receiver, description))
            await conn.commit()

async def log_event_general(timestamp: datetime, level: LogLevel, receiver: str, description: str, pool_type: str = "fastapi"):
    """
    Logs events that are outside of task context, where task_id is not applicable.
    """
    await log_event(timestamp, level, "N/A", receiver, description, pool_type=pool_type)

async def fetch_logs_by_task_id(task_id: str):
    """
    Fetches logs associated with a specific task_id.
    """
    pool = await get_connection(pool_type="fastapi")
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                SELECT id, timestamp, log_level, task_id, receiver, description
                FROM logs
                WHERE task_id = %s
                ORDER BY id DESC
            """, (task_id,))
            rows = await cur.fetchall()
    return rows

async def fetch_logs_by_receiver(receiver: str):
    """
    Fetches logs associated with a specific receiver.
    """
    pool = await get_connection(pool_type="fastapi")
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                SELECT id, timestamp, log_level, task_id, receiver, description
                FROM logs
                WHERE receiver = %s
                ORDER BY id DESC
            """, (receiver,))
            rows = await cur.fetchall()
    return rows

async def fetch_all_logs():
    """
    Fetches all logs from the logs table.
    """
    pool = await get_connection(pool_type="fastapi")
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                SELECT timestamp, log_level, task_id, receiver, description
                FROM logs
                ORDER BY id DESC
            """)
            rows = await cur.fetchall()
    return rows

def log_level_as_span(level_str: str) -> str:
    """
    Converts a log level string into an HTML span with appropriate styling.
    """
    level_upper = level_str.upper()
    if level_upper == "SUCCESS":
        return f"<span class='btn btn-success btn-sm'>{level_str}</span>"
    elif level_upper == "ERROR":
        return f"<span class='btn btn-danger btn-sm'>{level_str}</span>"
    elif level_upper == "WARNING":
        return f"<span class='btn btn-warning btn-sm'>{level_str}</span>"
    elif level_upper == "INFO":
        return f"<span class='btn btn-info btn-sm'>{level_str}</span>"
    else:
        return f"<span class='btn btn-secondary btn-sm'>{level_str}</span>"
