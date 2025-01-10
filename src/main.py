import csv
import os
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from datetime import datetime
from .tasks import send_lectio_msg
from .tasks import celery_app


LOG_FILE_PATH = "/app/src/logs/logs.csv"

app = FastAPI(
    title="Lectio Message Sender",
    description="API for sending messages via Lectio with async Celery tasks, now with user-supplied credentials.",
    version="1.0.0"
)


class MessageRequest(BaseModel):
    lectio_school_id: str
    lectio_user: str
    lectio_password: str
    send_to: str
    subject: str
    body: str
    can_be_replied: bool = True


@app.get("/", response_class=HTMLResponse, tags=["Health"])
def health_check():
    """
    A simple health-check endpoint.
    """
    return {"status": "ok", "timestamp": datetime.now()}

@app.get("/workers", tags=["Workers"])
def get_workers_status():
    """
    Ping the Celery workers to see which are alive.
    Returns a dictionary of {worker_name: 'pong'} if they're up.
    """
    insp = celery_app.control.inspect()

    # Ping all workers
    ping_result = insp.ping()

    if not ping_result:
        return JSONResponse(
            status_code=503,
            content={
                "status": "No workers found or unable to connect",
                "timestamp": str(datetime.now())
            }
        )

    # If there is a result, it should be something like:
    # {"celery@workerhostname": {"ok": "pong"}}
    return {
        "status": "Workers responding",
        "timestamp": str(datetime.now()),
        "workers": ping_result
    }


@app.post("/send-message", tags=["Messages"])
def api_send_message(request: MessageRequest):
    """
    Send a Lectio message with the provided login info and message details.
    The message is enqueued for Celery to send in the background.
    """
    task = send_lectio_msg.delay(
        lectio_school_id=request.lectio_school_id,
        lectio_user=request.lectio_user,
        lectio_password=request.lectio_password,
        send_to=request.send_to,
        subject=request.subject,
        message=request.body,
        can_be_replied=request.can_be_replied
    )
    return {"task_id": task.id, "status": "Task submitted"}


@app.get("/logs", response_class=HTMLResponse, tags=["Logs"])
def get_logs_pretty():
    """
    Reads the CSV log file and returns a Bootstrap-styled HTML table,
    showing newest entries first. The log_level is displayed as
    Bootstrap button badges.
    """
    if not os.path.exists(LOG_FILE_PATH):
        return """
        <h3 style="margin:20px;">Ingen logfil fundet.</h3>
        """

    # Read all CSV rows
    with open(LOG_FILE_PATH, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)

    if len(rows) < 2:
        return """
        <h3 style="margin:20px;">Logfilen er tom eller indeholder kun en header.</h3>
        """

    # First row is assumed to be the header: ["timestamp", "log_level", "task_id", "receiver", "description", ...]
    header = rows[0]
    data_rows = rows[1:]

    # Reverse data_rows so the newest entries appear first
    data_rows.reverse()

    # We can define a helper to map log levels to Bootstrap classes
    def get_level_button(level_text: str) -> str:
        level_text_upper = level_text.upper()
        if level_text_upper == "SUCCESS":
            btn_class = "btn-success"
        elif level_text_upper == "ERROR":
            btn_class = "btn-danger"
        elif level_text_upper == "INFO":
            btn_class = "btn-info"
        else:
            btn_class = "btn-secondary"
        return f'<button class="btn {btn_class} btn-sm" disabled>{level_text}</button>'

    # Build table header
    table_header = "".join(f"<th>{col}</th>" for col in header)

    # Build table body rows
    table_body = ""
    for row in data_rows:
        # row order assumed: [timestamp, log_level, task_id, receiver, description, ...]
        # We specifically style column #1 (log_level) with a Bootstrap button
        if len(row) >= 2:
            # row[1] is log_level
            level_html = get_level_button(row[1])
            # Rebuild the row, replacing row[1] with our custom HTML
            new_row = [
                row[0],
                level_html,      # replaced log_level text with button
                *row[2:]         # task_id, receiver, description, etc.
            ]
        else:
            # If row doesn't have enough columns, just display raw
            new_row = row

        # Build HTML <td> for each column
        row_html = "".join(f"<td>{col}</td>" for col in new_row)
        table_body += f"<tr>{row_html}</tr>"

    # Construct final HTML with Bootstrap
    html_content = f"""
    <html>
      <head>
        <meta charset="utf-8"/>
        <title>Lectio Message Logs</title>
        <!-- Bootstrap CSS (via CDN) -->
        <link rel="stylesheet"
              href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css"
              integrity="sha384-ENjdO4Dr2bkBIFxQpeo1bSMgkVObLkE5oXavPUCl+Pkb3gfq6nXCKFNQBVSh+JY+"
              crossorigin="anonymous">
      </head>
      <body class="bg-light">
        <div class="container my-4">
          <h2 class="mb-4">Lectio Message Logs</h2>
          <div class="table-responsive">
            <table class="table table-bordered table-striped table-hover">
              <thead class="table-dark">
                <tr>{table_header}</tr>
              </thead>
              <tbody>
                {table_body}
              </tbody>
            </table>
          </div>
        </div>
      </body>
    </html>
    """
    return html_content
