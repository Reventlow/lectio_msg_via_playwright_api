import psycopg
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from datetime import datetime
from asyncio import sleep
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

    return [
        {
            "id": row[0],
            "timestamp": row[1].isoformat() if row[1] else None,
            "log_level": row[2],
            "task_id": row[3],
            "receiver": row[4],
            "description": row[5]
        }
        for row in rows
    ]

@app.get("/logs/by_receiver/{receiver}", tags=["Logs"])
def get_logs_by_receiver(receiver: str):
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

    return [
        {
            "id": row[0],
            "timestamp": row[1].isoformat() if row[1] else None,
            "log_level": row[2],
            "task_id": row[3],
            "receiver": row[4],
            "description": row[5]
        }
        for row in rows
    ]

@app.get("/logs", response_class=HTMLResponse, tags=["Logs"])
def get_logs_pretty():
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

    tbody_rows = ""
    for row in rows:
        ts, level, task_id, receiver, description = row
        timestamp_str = ts.isoformat() if ts else ""
        level_span = log_level_as_span(level)

        tbody_rows += f"""
          <tr>
            <td>{timestamp_str}</td>
            <td>{level_span}</td>
            <td>{task_id or ''}</td>
            <td>{receiver or ''}</td>
            <td>{description or ''}</td>
          </tr>
        """

    html_content = f"""
<html>
<head>
  <meta charset="utf-8"/>
  <title>Lectio API Message Logs</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet" 
    integrity="sha384-QWTKZyjpPEjISv5WaRU9OFeRpok6YctnYmDr5pNlyT2bRjXh0JMhjY6hW+ALEwIH" crossorigin="anonymous">
</head>
<body class="p-4">
  <div class="container">
    <h2 class="mb-4">Lectio API Message Logs</h2>
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
</body>
</html>
    """
    return html_content


@app.websocket("/ws/dashboard")
async def websocket_dashboard(websocket: WebSocket):
    await websocket.accept()
    from celery import Celery
    celery_app = Celery(broker="redis://redis:6379/0")
    inspector = celery_app.control.inspect()

    try:
        while True:
            active = inspector.active() or {}
            reserved = inspector.reserved() or {}
            stats = inspector.stats() or {}
            scheduled = inspector.scheduled() or {}

            workers_status = {}
            for worker, worker_stats in stats.items():
                # Retrieve task lists for this worker (could be empty lists)
                active_tasks = active.get(worker, [])
                reserved_tasks = reserved.get(worker, [])
                scheduled_tasks = scheduled.get(worker, [])

                # Sort each list by 'id' (if present). Some celery versions store 'id',
                # older versions might store 'task_id'. Adjust accordingly.
                active_tasks.sort(key=lambda t: t.get('id', ''))
                reserved_tasks.sort(key=lambda t: t.get('id', ''))
                scheduled_tasks.sort(key=lambda t: t.get('id', ''))

                workers_status[worker] = {
                    "active_tasks": active_tasks,
                    "reserved_tasks": reserved_tasks,
                    "scheduled_tasks": scheduled_tasks,
                    "status": "Online"
                }

            queue_status = {
                "scheduled": scheduled,
                "reserved": reserved,
                "active": active,
            }

            await websocket.send_json({
                "timestamp": datetime.now().isoformat(),
                "workers": workers_status,
                "queue": queue_status
            })

            await sleep(5)
    except WebSocketDisconnect:
        print("WebSocket disconnected")
    except Exception as e:
        print(f"Error in WebSocket: {e}")
    finally:
        await websocket.close()

@app.get("/dashboard", response_class=HTMLResponse, tags=["Dashboard"])
def get_dashboard():
    html_content = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LECTIO API Real-Time Dashboard</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 20px;
        }
        h1, h2 {
            text-align: center;
        }
        pre {
            background-color: #f4f4f4;
            padding: 10px;
            border-radius: 5px;
            overflow: auto;
            max-height: 300px;
        }
    </style>
</head>
<body>
    <h1>LECTIO API Real-Time Dashboard</h1>

    <div id="worker-status">
        <h2>Worker Status</h2>
        <pre id="worker-data">Loading...</pre>
    </div>



    <script>
        const ws = new WebSocket("ws://10.18.225.150:8010/ws/dashboard");

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            const { timestamp, workers, queue } = data;

            document.getElementById("worker-data").textContent = JSON.stringify(workers, null, 2);
            document.getElementById("queue-data").textContent = JSON.stringify(queue, null, 2);
        };

        ws.onerror = (event) => {
            console.error("WebSocket error:", event);
            document.getElementById("worker-data").textContent = "Error fetching worker data.";
            document.getElementById("queue-data").textContent = "Error fetching queue data.";
        };

        ws.onclose = () => {
            console.log("WebSocket connection closed");
            document.getElementById("worker-data").textContent = "WebSocket connection closed.";
            document.getElementById("queue-data").textContent = "WebSocket connection closed.";
        };
    </script>
</body>
</html>
    """
    return HTMLResponse(content=html_content)

def log_level_as_span(level_str: str) -> str:
    level_upper = level_str.upper()
    if level_upper == "SUCCESS":
        return f"<span class='btn btn-success btn-sm'>{level_str}</span>"
    elif level_upper == "ERROR":
        return f"<span class='btn btn-danger btn-sm'>{level_str}</span>"
    elif level_upper == "INFO":
        return f"<span class='btn btn-info btn-sm'>{level_str}</span>"
    else:
        return f"<span class='btn btn-secondary btn-sm'>{level_str}</span>"
