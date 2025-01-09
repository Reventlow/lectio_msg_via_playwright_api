# Lectio Besked Sender

Dette projekt giver mulighed for at sende beskeder via Lectio's hjemmeside ved hjælp af Python, Playwright og nu også FastAPI og Celery for at håndtere beskedafsendelser asynkront og mere skalerbart.  

## Indholdsfortegnelse

1. [Introduktion](#introduktion)  
2. [Krav](#krav)  
3. [Installation (lokalt)](#installation-lokalt)  
4. [Kørsel med Docker Compose](#kørsel-med-docker-compose)  
5. [Brug af API’et](#brug-af-apiet)  
6. [Test](#test)  
7. [Fejlfinding](#fejlfinding)  
8. [Licens](#licens)

---

## Introduktion

Dette projekt indeholder en FastAPI-baseret HTTP-server, der kan modtage anmodninger om at sende en besked til en Lectio-bruger.  
Selve afsendelsen varetages af en Celery-worker, der bruger Playwright til at logge ind i Lectio og sende beskeden.  

Fordelene ved dette setup er:  
- **Asynkrone beskeder** (Celery): Beskeder kan sendes i baggrunden, uden at API’et blokerer.  
- **Skalerbarhed** (Celery + Docker): Du kan køre flere Celery-workers samtidigt og dermed håndtere flere beskedanmodninger parallelt.  
- **Automatisk dokumentation** (FastAPI): Der genereres OpenAPI/Swagger-dokumentation, så du nemt kan teste og dokumentere dit API.  

---

## Krav

- **Python** 3.12 eller nyere (lokal kørsel)  
- **Playwright** (til browser-automatisering)  
- **Celery** (håndterer baggrundsopgaver)  
- **Redis** (eller en anden broker) hvis du vil køre Celery i produktion.  

> Bemærk, at hvis du kører via Docker Compose, vil disse krav blive håndteret automatisk af containerne.

---

## Installation (lokalt)

Hvis du ønsker at køre projektet lokalt (uden Docker), kan du følge disse trin:

1. **Klon projektet til din lokale maskine**  
   ```bash
   git clone https://github.com/Reventlow/lectio_msg_via_playwright_api
   ```
2. **Naviger ind i projektets mappe**  
   ```bash
   cd <project-folder>
   ```
3. **Installer de nødvendige Python-biblioteker**  
   ```bash
   pip install -r requirements.txt
   ```
4. **Installér Playwright samt browser-binære**  
   ```bash
   playwright install
   ```
5. **Kør FastAPI-appen**  
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```
   API’et er nu tilgængeligt på `http://localhost:8000/`.

6. **Kør Celery-worker** (kræver en kørende Redis eller anden broker; justér URL efter dit setup):  
   ```bash
   celery -A app.tasks.celery_app worker --loglevel=INFO --concurrency=4
   ```
   Så er dine Celery-workers klar til at tage imod opgaver.

---

## Kørsel med Docker Compose

For nem installation og skalering kan du bruge Docker Compose. Et eksempel på en `docker-compose.yml` inkluderer:  
- En **FastAPI-service** (`lectio_api`),  
- En **Celery Worker-service** (`lectio_worker`),  
- En **Redis-service** (`redis`) som broker for Celery.  

1. **Sørg for, at du har** Docker og Docker Compose installeret.  
2. **Klon projektet**, og gå til projektmappen.  
3. **Kør**:
   ```bash
   docker-compose up --build
   ```
   Dette vil starte:  
   - **API’et** på `http://localhost:8000`  
   - **Celery-worker**(s)  
   - **Redis**  

For at skalere antallet af Celery-workers, kan du enten:  
- I Docker Swarm: Tilføje `replicas: 10` i `docker-compose.yml` under `deploy`, eller  
- I normal Compose: `docker-compose up --scale lectio_worker=10`.

---

## Brug af API’et

Når FastAPI kører, kan du se den automatiske dokumentation på:  
- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)  
- **Redoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

### 1. Health-check  
- **Endpoint**: `GET /`  
- **Beskrivelse**: Returnerer status=ok og et timestamp.

### 2. Send en besked  
- **Endpoint**: `POST /send-message`  
- **Body (JSON)**:
  ```json
  {
    "send_to": "Modtagerens navn",
    "subject": "Emne",
    "body": "Beskedens indhold",
    "can_be_replied": true
  }
  ```
- **Eksempel CURL**:
  ```bash
  curl -X POST http://localhost:8000/send-message \
  -H 'Content-Type: application/json' \
  -d '{
    "lectio_school_id": "234",
    "lectio_user": "demo_user",
    "lectio_password": "secret_password",
    "send_to": "RPA øh",
    "subject": "Test from API",
    "body": "This is a test message from the new API-based credentials approach.",
    "can_be_replied": false
  }'

  ```
- **Response**:  
  ```json
  {
    "task_id": "d50fe5eb-3d48-4ac9-a53e-...",
    "status": "Task submitted"
  }
  ```
  Du modtager en `task_id`, som angiver den Celery-job, der sender beskeden i baggrunden.




- **Eksempel: Python `requests`:**

   ```python
   import requests
   
   # Definer API-endepunktet (lokalt) — juster, hvis du kører et andet sted
   API_URL = "http://localhost:8000/send-message"
   
   # Opret data, der skal sendes i request-body.
   # Her er et eksempel med brugerspecifikke credentials og beskedinfo
   payload = {
       "lectio_school_id": "234",
       "lectio_user": "demo_user",
       "lectio_password": "secret_password",
       "send_to": "Test Bruger",        # Modtager
       "subject": "Hejsa fra Python",
       "body": "Dette er en testbesked via Python-requests",
       "can_be_replied": False
   }
   
   try:
       # Udfører POST-request til FastAPI-endepunktet
       response = requests.post(API_URL, json=payload)
   
       # Tjek for HTTP-status
       if response.status_code == 200:
           # Print JSON-svar, f.eks. { "task_id": "...", "status": "Task submitted" }
           print("Besked anmodning succesfuld:")
           print(response.json())
       else:
           print(f"Fejl ved afsendelse, status_code: {response.status_code}")
           print(response.text)
   
   except requests.exceptions.RequestException as e:
       print(f"Netværksfejl: {e}")
   ```
  
## Test

Projektet indeholder en række **pytest**-tests (inkl. `pytest-mock`) for at teste både API-endepunkter, Celery-tasks og hjælpefunktioner.  

1. **Installer testafhængigheder** (de ligger også i `requirements.txt`):  
   ```bash
   pip install -r requirements.txt
   ```
2. **Kør tests**:
   ```bash
   pytest --maxfail=1 --disable-warnings -q
   ```
   Dette vil køre alle testfiler i mappen `tests/`.

Nogle eksempler på testfiler:
- `test_main.py` tester FastAPI-endepunkter med `TestClient`.
- `test_tasks.py` tester Celery-tasks.
- `test_logs.py` tester log-funktionen.
- `test_lectio.py` tester LectioBot-funktioner.

---

## Live Log View (Web)

For nemt at se loggen over sendte beskeder, har vi tilføjet et endpoint `/logs`:

1. Start API’et:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```
2. Gå til http://localhost:8000/logs i din browser.
3. Du vil se en tabel, der viser alle log-linjer fra logs.csv.

   *Dette giver en hurtig og nem oversigt over tidspunkter, beskedstatus og mere*
---

## Fejlfinding

1. **Manglende moduler**  
   - Kontroller at alle Python-afhængigheder er installeret (`pip install -r requirements.txt`).  
   - Kontroller at Playwright-browserne er installeret (`playwright install`).  
2. **Problemer med Celery/Redis**  
   - Sørg for, at din Redis-service kører (enten via Docker eller lokalt).  
   - Tjek din `CELERY_BROKER_URL` (typisk `redis://redis:6379/0`).  
3. **Timeout- eller loginfejl på Lectio**  
   - Tjek dine Lectio-legitimationsoplysninger (brugernavn, adgangskode, school_id).  
   - Kontroller, at netværksforbindelse og server-URL’er er korrekte.  

---

## Licens

Dette projekt er licenseret under [MIT-licensen](https://opensource.org/licenses/MIT).  

Du er velkommen til at bidrage med fejlrettelser og nye funktioner via pull requests. Har du spørgsmål, er du velkommen til at åbne et issue eller kontakte os direkte.  

**God fornøjelse med projektet!**