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
    ERROR = "ERROR"

# Retrieve connection details from environment variables
POSTGRES_HOST = get_env_variable("POSTGRES_HOST", default_value="db")
POSTGRES_DB = get_env_variable("POSTGRES_DB", default_value="logsdb")
POSTGRES_USER = get_env_variable("POSTGRES_USER", default_value="myuser")
POSTGRES_PASSWORD = get_env_variable("POSTGRES_PASSWORD", default_value="mypass")
POSTGRES_PORT = get_env_variable("POSTGRES_PORT", default_value="5432")  # Default PostgreSQL port

# Initialize the asynchronous connection pool
connection_pool = AsyncConnectionPool(
    min_size=1,
    max_size=10,
    host=POSTGRES_HOST,
    port=POSTGRES_PORT,
    dbname=POSTGRES_DB,
    user=POSTGRES_USER,
    password=POSTGRES_PASSWORD
)

async def init_logs_table():
    """
    Creates the logs table if it doesn't exist.
    """
    async with connection_pool.connection() as conn:
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

async def log_event(timestamp: datetime, level: LogLevel, task_id: str, receiver: str, description: str):
    """
    Writes a log entry to the PostgreSQL database asynchronously.
    """
    async with connection_pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                INSERT INTO logs (timestamp, log_level, task_id, receiver, description)
                VALUES (%s, %s, %s, %s, %s)
            """, (timestamp, level.value, task_id, receiver, description))
            await conn.commit()

async def log_event_general(timestamp: datetime, level: LogLevel, receiver: str, description: str):
    """
    Logs events that are outside of task context, where task_id is not applicable.
    """
    await log_event(timestamp, level, "N/A", receiver, description)
