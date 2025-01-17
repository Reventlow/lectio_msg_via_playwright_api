# tasks.py

from celery import Celery, Task
from datetime import datetime
from .logs import log_event, LogLevel
from .lectio import LectioBot
from .import_env import get_env_variable
import os

CELERY_BROKER_URL = get_env_variable("CELERY_BROKER_URL") or "redis://redis:6379/0"
CELERY_BACKEND_URL = get_env_variable("CELERY_BACKEND_URL") or "redis://redis:6379/1"

celery_app = Celery(
    "lectio_sender",
    broker=CELERY_BROKER_URL,
    backend=CELERY_BACKEND_URL
)

APPLITOOLS_IS_ACTIVE = (
    True if get_env_variable("APPLITOOLS_IS_ACTIVE") == "True" else False
)
APPLITOOLS_API_KEY = get_env_variable("APPLITOOLS_API_KEY") or None

class BaseTaskWithLogging(Task):
    """
    Custom Task class that includes logging before and after task execution.
    """

    def on_success(self, retval, task_id, args, kwargs):
        # Log successful completion if not already logged
        log_event(
            timestamp=datetime.now(),
            level=LogLevel.SUCCESS,
            task_id=task_id,
            receiver=kwargs.get("send_to", "Unknown"),
            description=f"Task {task_id} completed successfully."
        )
        super().on_success(retval, task_id, args, kwargs)

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        # Log failure
        log_event(
            timestamp=datetime.now(),
            level=LogLevel.ERROR,
            task_id=task_id,
            receiver=kwargs.get("send_to", "Unknown"),
            description=f"Task {task_id} failed with error: {str(exc)}"
        )
        super().on_failure(exc, task_id, args, kwargs, einfo)

@celery_app.task(bind=True, base=BaseTaskWithLogging, max_retries=20, default_retry_delay=5)
def send_lectio_msg(
    self,
    lectio_school_id: str,
    lectio_user: str,
    lectio_password: str,
    send_to: str,
    subject: str,
    message: str,
    can_be_replied: bool
):
    """
    Celery task to send a message via Lectio using Celery's retry mechanism.
    """
    task_id = self.request.id  # unique Celery task identifier

    # Log that we are starting
    log_event(
        timestamp=datetime.now(),
        level=LogLevel.INFO,
        task_id=task_id,
        receiver=send_to,
        description=f"Starting to send Lectio message to {send_to}."
    )

    try:
        # Create a LectioBot instance with user-supplied credentials
        lectio_session = LectioBot(
            school_id=lectio_school_id,
            lectio_user=lectio_user,
            lectio_password=lectio_password,
            browser_headless=True,
            applitools_is_active=APPLITOOLS_IS_ACTIVE,
            applitools_api_key=APPLITOOLS_API_KEY,
            applitools_app_name='lectio_msg_sender',
            applitools_test_name=f'Send msg at {datetime.now()}'
        )

        # Send the message
        lectio_session.send_message(
            send_to=send_to,
            subject=subject,
            msg=message,
            can_be_replied=can_be_replied
        )

        # If successful, log success (handled by on_success)

    except Exception as e:
        # Log the error with INFO level indicating a retry attempt
        log_event(
            timestamp=datetime.now(),
            level=LogLevel.INFO,
            task_id=task_id,
            receiver=send_to,
            description=f"Flow attempt {self.request.retries + 1}/20 failed with error: {str(e)}. Will retry..."
        )
        try:
            # Retry the task
            self.retry(exc=e)
        except self.MaxRetriesExceededError:
            # Log final failure after all retries
            log_event(
                timestamp=datetime.now(),
                level=LogLevel.ERROR,
                task_id=task_id,
                receiver=send_to,
                description=f"Task {task_id} failed after {self.request.retries} retries."
            )
            raise e  # Ensure the task is marked as failed in Celery
