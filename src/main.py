# main.py

import psycopg
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from datetime import datetime
from typing import List
from .tasks import send_lectio_msg
from .logs import init_logs_table, get_connection

app = FastAPI(
    title="Lectio Message Sender",
    description="API for sending messages via Lectio with async Celery tasks, storing logs in PostgreSQL.",
    version="1.0.0"
)

# Initialize logs table at startup
@app.on_event("startup")
def startup_event():
    init_logs_table()

class MessageRequest(BaseModel):
    lectio_school_id: str
    lectio_user: str
    lectio_password: str
    send_to: str
    subject: str
    body: str
    can_be_replied: bool = True

@app.get("/", tags=["Health"])
def health_check():
    return {"status": "ok", "timestamp": datetime.now()}

@app.post("/send-message", tags=["Messages"])
def api_send_message(request: MessageRequest):
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

@app.get("/logs/by_task_id/{task_id}", tags=["Logs"])
def get_logs_by_task_id(task_id: str):
    """
    Returns all log entries for a given task_id.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, timestamp, log_level, task_id, receiver, description
                FROM logs
                WHERE task_id = %s
                ORDER BY id DESC
            """, (task_id,))
            rows = cur.fetchall()
    finally:
        conn.close()

    results = []
    for r in rows:
        results.append({
            "id": r[0],
            "timestamp": r[1].isoformat() if r[1] else None,
            "log_level": r[2],
            "task_id": r[3],
            "receiver": r[4],
            "description": r[5]
        })
    return results

@app.get("/logs/by_receiver/{receiver}", tags=["Logs"])
def get_logs_by_receiver(receiver: str):
    """
    Returns all log entries for a given receiver.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, timestamp, log_level, task_id, receiver, description
                FROM logs
                WHERE receiver = %s
                ORDER BY id DESC
            """, (receiver,))
            rows = cur.fetchall()
    finally:
        conn.close()

    results = []
    for r in rows:
        results.append({
            "id": r[0],
            "timestamp": r[1].isoformat() if r[1] else None,
            "log_level": r[2],
            "task_id": r[3],
            "receiver": r[4],
            "description": r[5]
        })
    return results

@app.get("/logs", response_class=HTMLResponse, tags=["Logs"])
def get_logs_pretty():
    """
    Reads the logs from PostgreSQL and returns a Bootstrap-styled HTML table.
    Shows newest entries first.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT timestamp, log_level, task_id, receiver, description
                FROM logs
                ORDER BY id DESC
            """)
            rows = cur.fetchall()
    finally:
        conn.close()

    # Build the <tbody> dynamically
    tbody_rows = ""
    for row in rows:
        ts, level, task_id, receiver, description = row
        timestamp_str = ts.isoformat() if ts else ""
        level_span = log_level_as_span(level)  # We'll define a helper below

        tbody_rows += f"""
          <tr>
            <td>{timestamp_str}</td>
            <td>{level_span}</td>
            <td>{task_id or ''}</td>
            <td>{receiver or ''}</td>
            <td>{description or ''}</td>
          </tr>
        """

    # Build final HTML
    html_content = f"""
<html>
<head>
  <meta charset="utf-8"/>
  <title>Lectio Message Logs</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet" 
    integrity="sha384-QWTKZyjpPEjISv5WaRU9OFeRpok6YctnYmDr5pNlyT2bRjXh0JMhjY6hW+ALEwIH" crossorigin="anonymous">
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
  <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js" 
    integrity="sha384-YvpcrYf0tY3lHB60NNkmXc5s9fDVZLESaAA55NDzOxhy9GkcIdslK1eN7N6jIeHz" crossorigin="anonymous">
  </script>
  <!-- Optionally auto-refresh every 10 seconds -->
  <!-- <script>
    setTimeout(() => {{ window.location.reload(); }}, 10000);
  </script> -->
</body>
</html>
    """
    return html_content

def log_level_as_span(level_str: str) -> str:
    """
    Converts the log_level (e.g. SUCCESS, INFO, ERROR) into a colored <span>.
    """
    level_upper = level_str.upper()
    if level_upper == "SUCCESS":
        return f"<span class='btn btn-success btn-sm'>{level_str}</span>"
    elif level_upper == "ERROR":
        return f"<span class='btn btn-danger btn-sm'>{level_str}</span>"
    elif level_upper == "INFO":
        return f"<span class='btn btn-info btn-sm'>{level_str}</span>"
    else:
        return f"<span class='btn btn-secondary btn-sm'>{level_str}</span>"
