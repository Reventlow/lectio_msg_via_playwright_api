import csv
import os
from datetime import datetime
from enum import Enum

LOG_FILE_PATH = "logs.csv"  # adjust as needed

class LogLevel(str, Enum):
    SUCCESS = "SUCCESS"
    INFO = "INFO"
    ERROR = "ERROR"

def log_event(timestamp: datetime, level: LogLevel, task_id: str, receiver: str, description: str):
    """
    Saves a line of log info to a CSV file.
    Format: timestamp, log level, task id, receiver, description
    """

    # Ensure directory or file exists
    file_exists = os.path.isfile(LOG_FILE_PATH)

    with open(LOG_FILE_PATH, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        # if file didn't exist, write a header row
        if not file_exists:
            writer.writerow(["timestamp", "log_level", "task_id", "receiver", "description"])

        writer.writerow([timestamp.isoformat(), level, task_id, receiver, description])
