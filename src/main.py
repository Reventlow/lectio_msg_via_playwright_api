from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from datetime import datetime
import csv
import os

from .tasks import send_lectio_msg

LOG_FILE_PATH = "logs.csv"

app = FastAPI(
    title="Lectio Message Sender",
    description="API for sending messages via Lectio with async Celery tasks, now with user-supplied credentials.",
    version="1.0.0"
)

class MessageRequest(BaseModel):
    # Lectio-kontooplysninger, der nu sendes via API:
    lectio_school_id: str
    lectio_user: str
    lectio_password: str

    # Beskeddetaljer:
    send_to: str
    subject: str
    body: str
    can_be_replied: bool = True

@app.get("/", tags=["Health"])
def health_check():
    """
    Simpelt health-check endpoint.
    """
    return {"status": "ok", "timestamp": datetime.now()}

@app.post("/send-message", tags=["Messages"])
def api_send_message(request: MessageRequest):
    """
    Sender en Lectio-besked med de angivne login-oplysninger og beskeddetaljer.
    Anvend Celery i baggrunden.
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
    Læser CSV-logfilen og returnerer en pæn Bootstrap-tabel.
    Viser nyeste log først, log_level er en 'knap', og skifter baggrundsfarve for hver række.
    """
    if not os.path.exists(LOG_FILE_PATH):
        return "<h3>Ingen logfil fundet.</h3>"

    # Læs hele CSV-filen
    with open(LOG_FILE_PATH, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)

    if len(rows) < 2:
        return "<h3>Logfilen er tom eller indeholder kun en header.</h3>"

    # Første række antages at være header
    header = rows[0]
    data_rows = rows[1:]

    # For at vise nyeste log først, vend rækkefølgen
    data_rows.reverse()

    # Funktion til at mappe log level -> Bootstrap button classes
    def get_btn_class(level: str) -> str:
        level_upper = level.upper()
        if level_upper == "SUCCESS":
            return "btn btn-success btn-sm"
        elif level_upper == "ERROR":
            return "btn btn-danger btn-sm"
        elif level_upper == "INFO":
            return "btn btn-info btn-sm"
        else:
            return "btn btn-secondary btn-sm"

    # Byg table head (med sort baggrund + hvid tekst)
    # NB: Vi bruger Bootstrap classes på thead for at få styling
    table_header_html = "".join(f"<th>{col}</th>" for col in header)
    table_header = f"""
      <thead class="bg-dark text-white">
        <tr>{table_header_html}</tr>
      </thead>
    """

    # Byg body-rows
    table_body = ""
    for row in data_rows:
        # row forventes at være: [timestamp, log_level, task_id, receiver, description]
        timestamp, log_level, task_id, receiver, description = row

        # Udskift log_level-cellen med en "knap"
        btn_class = get_btn_class(log_level)
        log_level_btn_html = f"<button class='{btn_class}' disabled>{log_level}</button>"

        # Byg HTML for hver celle
        row_html = f"""
          <td>{timestamp}</td>
          <td>{log_level_btn_html}</td>
          <td>{task_id}</td>
          <td>{receiver}</td>
          <td>{description}</td>
        """
        table_body += f"<tr>{row_html}</tr>"

    # Indsæt body i <tbody> og brug Bootstrap .table-striped til at skifte baggrund
    table_body = f"<tbody>{table_body}</tbody>"

    # Byg endeligt HTML-indhold med Bootstrap
    html_content = f"""
    <html>
    <head>
      <meta charset="utf-8"/>
      <title>Lectio Message Logs</title>
      <!-- Bootstrap CSS -->
      <link
        rel="stylesheet"
        href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css"
        integrity="sha384-ENjdO4Dr2bkBIFxQpeoKl2CWynvZp1C83uZFrG7c4I3z9IGxU0NJoBDevdvuLGfn"
        crossorigin="anonymous"
      >
    </head>
    <body class="p-4">
      <div class="container">
        <h2 class="mb-4">Lectio Message Logs</h2>
        <table class="table table-striped table-bordered table-hover">
          {table_header}
          {table_body}
        </table>
      </div>
    </body>
    </html>
    """
    return html_content
