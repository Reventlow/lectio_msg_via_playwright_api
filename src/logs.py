import os
import csv
from datetime import datetime
from enum import Enum

LOG_FILE_PATH = "/app/src/logs/logs.csv"

class LogLevel(str, Enum):
    SUCCESS = "SUCCESS"
    INFO = "INFO"
    ERROR = "ERROR"

def log_event(timestamp: datetime, level: LogLevel, task_id: str, receiver: str, description: str):
    
    print("Attempting to save to log to this file: " + LOG_FILE_PATH)
        
    # Make sure the directory exists
    dir_name = os.path.dirname(LOG_FILE_PATH)
    if not os.path.exists(dir_name):
        os.makedirs(dir_name)

    file_exists = os.path.isfile(LOG_FILE_PATH)
    with open(LOG_FILE_PATH, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["timestamp", "log_level", "task_id", "receiver", "description"])

        writer.writerow([timestamp.isoformat(), level, task_id, receiver, description])

    print("Log saved to this file: " + LOG_FILE_PATH)
