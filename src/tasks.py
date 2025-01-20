# tasks.py

from celery import Celery, Task
from datetime import datetime
from .logs import log_event, LogLevel, init_connection_pool, init_logs_table
from .import_env import get_env_variable
import asyncio
from lectio import LectioBot

# Celery Configuration
CELERY_BROKER_URL = get_env_variable("CELERY_BROKER_URL") or "redis://redis:6379/0"
CELERY_BACKEND_URL = get_env_variable("CELERY_BACKEND_URL") or "redis://redis:6379/1"

celery_app = Celery(
    "lectio_sender",
    broker=CELERY_BROKER_URL,
    backend=CELERY_BACKEND_URL
)

APPLITOOLS_IS_ACTIVE = get_env_variable("APPLITOOLS_IS_ACTIVE") == "True"
APPLITOOLS_API_KEY = get_env_variable("APPLITOOLS_API_KEY")


def run_async(coroutine):
    """
    Runs an asynchronous coroutine in a new event loop.

    Args:
        coroutine (coroutine): The coroutine to run.

    Returns:
        Any: The result of the coroutine.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coroutine)
    finally:
        loop.close()


class BaseTaskWithLogging(Task):
    """
    Custom Task class that includes logging before and after task execution.
    """

    def on_success(self, retval, task_id, args, kwargs):
        # Use the run_async helper to execute the coroutine
        run_async(log_event(
            timestamp=datetime.utcnow(),
            level=LogLevel.SUCCESS,
            task_id=task_id,
            receiver=kwargs.get("send_to", "Unknown"),
            description=f"Task {task_id} completed successfully.",
            pool_type="celery"
        ))
        super().on_success(retval, task_id, args, kwargs)

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        # Use the run_async helper to execute the coroutine
        run_async(log_event(
            timestamp=datetime.utcnow(),
            level=LogLevel.ERROR,
            task_id=task_id,
            receiver=kwargs.get("send_to", "Unknown"),
            description=f"Task {task_id} failed with error: {str(exc)}",
            pool_type="celery"
        ))
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
    run_async(
        log_event(
            timestamp=datetime.utcnow(),
            level=LogLevel.INFO,
            task_id=task_id,
            receiver=send_to,
            description=f"Starting to send Lectio message to {send_to}.",
            pool_type="celery"
        )
    )

    try:
        # Initialize the connection pool and logs table if not already done
        run_async(init_connection_pool(pool_type="celery"))
        run_async(init_logs_table(pool_type="celery"))

        # Create a LectioBot instance with user-supplied credentials
        lectio_session = LectioBot(
            school_id=lectio_school_id,
            lectio_user=lectio_user,
            lectio_password=lectio_password,
            browser_headless=True,
            applitools_is_active=APPLITOOLS_IS_ACTIVE,
            applitools_api_key=APPLITOOLS_API_KEY,
            applitools_app_name='lectio_msg_sender',
            applitools_test_name=f'Send msg at {datetime.utcnow()}'
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
        # Log the error with WARNING level indicating a retry attempt
        run_async(
            log_event(
                timestamp=datetime.utcnow(),
                level=LogLevel.WARNING,  # Changed from INFO to WARNING
                task_id=task_id,
                receiver=send_to,
                description=f"Flow attempt {self.request.retries + 1}/20 failed with error: {str(e)}. Will retry...",
                pool_type="celery"
            )
        )
        try:
            # Retry the task
            self.retry(exc=e)
        except self.MaxRetriesExceededError:
            # Log final failure after all retries
            run_async(
                log_event(
                    timestamp=datetime.utcnow(),
                    level=LogLevel.ERROR,
                    task_id=task_id,
                    receiver=send_to,
                    description=f"Task {task_id} failed after {self.request.retries} retries.",
                    pool_type="celery"
                )
            )
            raise e  # Ensure the task is marked as failed in Celery
