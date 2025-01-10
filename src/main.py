from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from datetime import datetime
import csv
import os

from .tasks import send_lectio_msg

LOG_FILE_PATH = "/app/src/logs/logs.csv"

app = FastAPI(
    title="Lectio Message Sender",
    description="API for sending messages via Lectio with async Celery tasks, now with user-supplied credentials.",
    version="1.0.0"
)

class MessageRequest(BaseModel):
    # Lectio login info:
    lectio_school_id: str
    lectio_user: str
    lectio_password: str

    # Message details:
    send_to: str
    subject: str
    body: str
    can_be_replied: bool = True

@app.get("/", tags=["Health"])
def health_check():
    """
    Simpel health check endpoint.
    """
    return {"status": "ok", "timestamp": datetime.now()}

@app.post("/send-message", tags=["Messages"])
def api_send_message(request: MessageRequest):
    """
    Sendes asynkront via Celery-task.
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
    Reads the CSV log file and returns the exact Bootstrap-based HTML snippet,
    showing newest entries first.
    """
    if not os.path.exists(LOG_FILE_PATH):
        return "<h3>Ingen logfil fundet.</h3>"

    with open(LOG_FILE_PATH, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)

    if len(rows) < 2:
        return "<h3>Logfilen er tom eller indeholder kun en header.</h3>"

    # Header row (assumed columns: timestamp, log_level, task_id, receiver, description)
    header = rows[0]
    data_rows = rows[1:]

    # Show newest logs first
    data_rows.reverse()

    # Helper to pick span class based on log level
    def level_span(level: str) -> str:
        level_upper = level.upper()
        if level_upper == "SUCCESS":
            return f"<span class='btn btn-success btn-sm'>{level}</span>"
        elif level_upper == "ERROR":
            return f"<span class='btn btn-danger btn-sm'>{level}</span>"
        elif level_upper == "INFO":
            return f"<span class='btn btn-info btn-sm'>{level}</span>"
        else:
            return f"<span class='btn btn-secondary btn-sm'>{level}</span>"

    # Build each <tr> in the table body
    tbody_rows = ""
    for row in data_rows:
        # row is expected to be [timestamp, log_level, task_id, receiver, description]
        timestamp, log_level, task_id, receiver, description = row

        tbody_rows += f"""
          <tr>
            <td>{timestamp}</td>
            <td>{level_span(log_level)}</td>
            <td>{task_id}</td>
            <td>{receiver}</td>
            <td>{description}</td>
          </tr>
        """

    # Now build the final HTML snippet exactly as given, inserting the dynamic rows
    html_content = f"""
<html>
<head>
  <meta charset="utf-8"/>
  <title>Lectio Message Logs</title>
  <!-- Bootstrap CSS -->
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet" integrity="sha384-QWTKZyjpPEjISv5WaRU9OFeRpok6YctnYmDr5pNlyT2bRjXh0JMhjY6hW+ALEwIH" crossorigin="anonymous">
</head>
<body class="p-4">
  <div class="container">
    <h2 class="mb-4">Lectio Message Logs</h2>
    <table class="table table-striped table-bordered table-hover">
      <thead class="bg-dark text-white">
        <tr><th>timestamp</th><th>log_level</th><th>task_id</th><th>receiver</th><th>description</th></tr>
      </thead>
      <tbody>
        {tbody_rows}
      </tbody>
    </table>
  </div>
  <!-- Bootstrap JS -->
  <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js" integrity="sha384-YvpcrYf0tY3lHB60NNkmXc5s9fDVZLESaAA55NDzOxhy9GkcIdslK1eN7N6jIeHz" crossorigin="anonymous"></script>
  <script src="https://cdn.jsdelivr.net/npm/@popperjs/core@2.11.8/dist/umd/popper.min.js" integrity="sha384-I7E8VVD/ismYTF4hNIPjVp/Zjvgyol6VFvRkX/vR+Vc4JQkC+hVqc2pM8ODewa9r" crossorigin="anonymous"></script>
  <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.min.js" integrity="sha384-0pUGZvbkm6XF6gxjEnlmuGrJXVbNuzT9qBBavbLwCsOGabYfZo0T0to5eqruptLy" crossorigin="anonymous"></script>
</body>
</html>
    """
    return html_content
