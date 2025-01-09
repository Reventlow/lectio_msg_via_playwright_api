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
    Reads the CSV log file and returns a Bootstrap + DataTables-based HTML page,
    with newest entries first and sortable columns.
    """
    if not os.path.exists(LOG_FILE_PATH):
        return HTMLResponse("<h3>Ingen logfil fundet.</h3>", status_code=200)

    with open(LOG_FILE_PATH, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)

    if len(rows) < 2:
        return HTMLResponse("<h3>Logfilen er tom eller indeholder kun en header.</h3>", status_code=200)

    # The first row is assumed to be the header
    header = rows[0]
    data_rows = rows[1:]

    # Reverse the order of data_rows so the newest entries appear first
    data_rows = data_rows[::-1]

    # Build the table header (Bootstrap + DataTables table)
    table_header = "".join(f"<th scope='col'>{col}</th>" for col in header)

    # Build the table body
    table_body = ""
    for row in data_rows:
        row_html = "".join(f"<td>{cell}</td>" for cell in row)
        table_body += f"<tr>{row_html}</tr>"

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8"/>
        <title>Lectio Message Logs</title>

        <!-- Bootstrap 5 CSS (CDN) -->
        <link 
          href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css"
          rel="stylesheet"
        />

        <!-- DataTables CSS (CDN) -->
        <link 
          rel="stylesheet"
          href="https://cdn.datatables.net/1.13.4/css/jquery.dataTables.min.css"
        />

        <style>
          body {{
            margin: 20px;
          }}
        </style>
    </head>
    <body>
        <div class="container-fluid">
            <h1 class="mb-4">Lectio Message Logs</h1>
            <div class="table-responsive">
                <table id="logsTable" class="table table-bordered table-striped align-middle">
                    <thead class="table-dark">
                        <tr>{table_header}</tr>
                    </thead>
                    <tbody>
                        {table_body}
                    </tbody>
                </table>
            </div>
        </div>

        <!-- jQuery (required for DataTables) -->
        <script 
          src="https://code.jquery.com/jquery-3.6.0.min.js"
          integrity="sha256-/xUj+3OJ+Y4xL2+3ea0uEpN4HUWe5KhKwf0NfGylV6w="
          crossorigin="anonymous">
        </script>

        <!-- Bootstrap 5 JS (CDN) -->
        <script 
          src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js">
        </script>

        <!-- DataTables JS (CDN) -->
        <script 
          src="https://cdn.datatables.net/1.13.4/js/jquery.dataTables.min.js">
        </script>

        <script>
          // Initialize DataTables once the DOM is ready
          $(document).ready(function() {{
              $('#logsTable').DataTable({{
                  "paging": false,       // If you want pagination, set to true
                  "ordering": true,      // Allows sorting by columns
                  "info": false,         // Hides "Showing X of Y entries"
                  "searching": true,     // If you want to remove search box, set to false
              }});
          }});
        </script>
    </body>
    </html>
    """

    return HTMLResponse(html_content)
