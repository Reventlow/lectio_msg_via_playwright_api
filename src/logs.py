# logs.py

import psycopg
from datetime import datetime
from enum import Enum
from os import getenv
from .import_env import get_env_variable

class LogLevel(str, Enum):
    SUCCESS = "SUCCESS"
    INFO = "INFO"
    ERROR = "ERROR"

# We'll retrieve connection details from environment variables
POSTGRES_HOST = get_env_variable("POSTGRES_HOST") or "localhost"
POSTGRES_DB = get_env_variable("POSTGRES_DB") or "logsdb"
POSTGRES_USER = get_env_variable("POSTGRES_USER") or "myuser"
POSTGRES_PASSWORD = get_env_variable("POSTGRES_PASSWORD") or "mypass"

def get_connection():
    return psycopg.connect(
        host=POSTGRES_HOST,
        dbname=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD
    )

def init_logs_table():
    """
    Creates the logs table if it doesn't exist.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS logs (
                    id SERIAL PRIMARY KEY,
                    timestamp TIMESTAMP NOT NULL,
                    log_level VARCHAR(20) NOT NULL,
                    task_id VARCHAR(255),
                    receiver VARCHAR(255),
                    description TEXT
                );
            """)
            conn.commit()
    finally:
        conn.close()

def log_event(timestamp: datetime, level: LogLevel, task_id: str, receiver: str, description: str):
    """
    Writes a log entry to the PostgreSQL database.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO logs (timestamp, log_level, task_id, receiver, description)
                VALUES (%s, %s, %s, %s, %s)
            """, (timestamp, level.value, task_id, receiver, description))
            conn.commit()
    finally:
        conn.close()
