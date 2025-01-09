# app/tasks.py

from celery import Celery
from datetime import datetime
from .logs import log_event, LogLevel
from .lectio import LectioBot
from .import_env import get_env_variable


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

@celery_app.task(bind=True)
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
    Celery task to send a message via Lectio, now using credentials passed from the API.
    """
    task_id = self.request.id  # unique Celery task identifier

    # Log start
    log_event(
        timestamp=datetime.now(),
        level=LogLevel.INFO,
        task_id=task_id,
        receiver=send_to,
        description=f"Starting to send Lectio message to {send_to}"
    )

    try:
        # Initialize the LectioBot with user-supplied credentials
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
        lectio_session.start_playwright()
        lectio_session.login_to_lectio()
        lectio_session.navigate_to_messages()

        # Send the message
        lectio_session.send_message(
            send_to=send_to,
            subject=subject,
            msg=message,
            this_msg_can_be_replied=can_be_replied
        )

        lectio_session.stop_playwright()

        # Log success
        log_event(
            timestamp=datetime.now(),
            level=LogLevel.SUCCESS,
            task_id=task_id,
            receiver=send_to,
            description=f"Successfully sent message to {send_to}"
        )

    except Exception as e:
        # Log error
        log_event(
            timestamp=datetime.now(),
            level=LogLevel.ERROR,
            task_id=task_id,
            receiver=send_to,
            description=f"Error sending message: {str(e)}"
        )
        raise e  # re-raise so Celery marks the task as failed
