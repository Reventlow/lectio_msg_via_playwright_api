# logs.py
import psycopg
from datetime import datetime
from enum import Enum
from os import getenv
from .import_env import get_env_variable
import os

class LogLevel(str, Enum):
    SUCCESS = "SUCCESS"
    INFO = "INFO"
    ERROR = "ERROR"

# We'll retrieve connection details from environment variables
POSTGRES_HOST = get_env_variable("POSTGRES_HOST", default_value="db")
POSTGRES_DB = get_env_variable("POSTGRES_DB", default_value="logsdb")
POSTGRES_USER = get_env_variable("POSTGRES_USER", default_value="myuser")
POSTGRES_PASSWORD = get_env_variable("POSTGRES_PASSWORD", default_value="mypass")
POSTGRES_PORT = get_env_variable("POSTGRES_PORT", default_value="5432")  # Default PostgreSQL port

# Use a connection pool for better performance
from psycopg.pool import SimpleConnectionPool

# Initialize the connection pool
connection_pool = SimpleConnectionPool(
    minconn=1,
    maxconn=10,
    host=POSTGRES_HOST,
    port=POSTGRES_PORT,
    dbname=POSTGRES_DB,
    user=POSTGRES_USER,
    password=POSTGRES_PASSWORD
)

def get_connection():
    """
    Retrieves a connection from the pool.
    """
    try:
        conn = connection_pool.getconn()
        return conn
    except Exception as e:
        print(f"Error obtaining database connection: {e}")
        raise e

def release_connection(conn):
    """
    Releases a connection back to the pool.
    """
    try:
        connection_pool.putconn(conn)
    except Exception as e:
        print(f"Error releasing database connection: {e}")

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
    except Exception as e:
        print(f"Error initializing logs table: {e}")
        conn.rollback()
        raise e
    finally:
        release_connection(conn)

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
    except Exception as e:
        print(f"Error logging event: {e}")
        conn.rollback()
        raise e
    finally:
        release_connection(conn)

def log_event_general(timestamp: datetime, level: LogLevel, receiver: str, description: str):
    """
    Logs events that are outside of task context, where task_id is not applicable.
    """
    log_event(timestamp, level, "N/A", receiver, description)
