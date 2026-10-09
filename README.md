# BYdoc

BYdoc is a healthcare discovery and outpatient appointment platform for patients, doctors, and clinics. Patients can find verified providers, review available slots and declared consultation fees, and receive a server-confirmed booking. The project includes separate role dashboards and an operational support flow.

> **Project status:** Active development. The repository is not ready for public production deployment. See [Deployment readiness](#deployment-readiness) for the remaining work.

## What works today

| Area | Current implementation |
| --- | --- |
| Patient accounts | Registration, password sign-in, one-time codes to a verified email or phone, optional Google sign-in, contact verification, password recovery, and profile editing. Browser API authentication uses short-lived JWT cookies and rotating refresh credentials. |
| Discovery and booking | Verified doctor and clinic discovery, a nearby clinic map with permission-based location access, live slots, short holds, fee review, and idempotent booking confirmation. PostgreSQL is the source of truth for appointment status. |
| Role dashboards | Separate patient, doctor, clinic, and platform-admin summaries with role-scoped data. |
| Support | Guided help for app tasks, support request submission, case references and status, and staff case administration. Optional private AI classifies free-text topics; patients receive reviewed answers. |
| Backend operations | Organization and clinic records, doctor verification data, notification outbox and inbox, preferences, audit-backed support cases, Celery jobs, and health checks. |

The frontend uses **Next.js**. The API and background jobs use **Django, Django REST Framework, and Celery**, with **PostgreSQL** for durable data and **Redis** for jobs and shared limits. Local development uses Docker Compose for PostgreSQL and Redis. The optional AI topic classifier uses a self-hosted Ollama service.

## Quick start (Windows PowerShell)

Prerequisites: Python 3.11, Node.js 22, and Docker Desktop. The commands below start from the repository root, with Docker Desktop running. These are the versions used in CI.

**Existing installations:** Keep your current `.env`. It preserves the original Compose project name and database identifiers so the BYdoc folder rename does not disconnect existing Docker volumes. New installations use the values in `.env.example`.

1. Create local configuration, replace the example development secrets in `.env`, and start PostgreSQL and Redis:

   ```powershell
   if (!(Test-Path .env)) { Copy-Item .env.example .env }
   # Edit .env and replace the sample local secrets before starting the services.
   docker compose up -d postgres redis
   docker compose ps
   ```

2. Start the API in a separate terminal:

   ```powershell
   cd backend
   python -m venv venv
   .\venv\Scripts\python.exe -m pip install -r requirements/development.txt
   .\venv\Scripts\python.exe manage.py migrate
   .\venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
   ```

3. Start the patient frontend in another terminal:

   ```powershell
   cd frontend
   if (!(Test-Path .env.local)) { Copy-Item .env.example .env.local }
   npm.cmd ci
   npm.cmd run dev
   ```

Open `http://localhost:3000`. Use `localhost` for both frontend and API so JWT cookies and CSRF work. The API base is `http://localhost:8000/api/v1/`; health endpoints are `/health/live/` and `/health/ready/`.

For email verification, password reset, and one-time code delivery, run a Celery worker and Beat in two more backend terminals. Development email is written to `backend/local-email`:

```powershell
# From backend, terminal 1
.\venv\Scripts\python.exe -m celery -A config worker --loglevel=INFO --pool=solo --concurrency=1 --without-mingle --without-gossip

# From backend, terminal 2
.\venv\Scripts\python.exe -m celery -A config beat --loglevel=INFO --schedule "$env:TEMP\bydoc-celerybeat-schedule"
```

See [authentication, OTP, and map setup](docs/otp-jwt-nearby.md) for login flows and launch configuration. Optional Google sign-in requires the same web client ID in root `.env` (`GOOGLE_OAUTH_CLIENT_ID`) and `frontend/.env.local` (`NEXT_PUBLIC_GOOGLE_CLIENT_ID`). Do not put a Google client secret in the frontend. SMS sign-in remains unavailable until an AWS sender and approved templates are configured; email codes work with the local email backend.

Guided help and support requests work without an AI model. To enable local topic classification, follow the [assistant setup](docs/ai-assistant.md). The model never writes a patient-facing answer or performs a booking action.

## Verify a local change

With PostgreSQL and Redis running, from `backend`:

```powershell
.\venv\Scripts\python.exe manage.py check
.\venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\venv\Scripts\python.exe -m pytest -q
```

From `frontend`:

```powershell
npm.cmd run typecheck
npm.cmd run build
```

GitHub Actions also checks backend translations and the OpenAPI schema, and builds the standalone frontend server. See the [backend](.github/workflows/backend-ci.yml) and [frontend](.github/workflows/frontend-ci.yml) workflows.

## Deployment readiness

The [AWS deployment design and release runbook](docs/aws-deployment.md) covers proposed infrastructure, secrets, containers, and release checks. Production settings and container images exist, but this repository does not provision AWS infrastructure. **Do not treat a passing build as approval to launch.** Remaining work includes:

- Provisioning and testing the production environment, HTTPS, email delivery, monitoring, backup restoration, and incident procedures.
- Completing clinic receptionist workflows, patient booking management, a full support inbox, and notification screens.
- Reviewing accessibility and Bengali/Hindi coverage, plus clinical safety testing of the assistant before public healthcare use.
- Registering and validating the SMS sender and approved templates, configuring a Google web client ID, and choosing a managed map tile service for production traffic.

PostgreSQL is authoritative for bookings: a selected slot, hold, or sent notification is not a confirmed appointment. BYdoc does not currently provide diagnosis, treatment, emergency care, prescriptions, medical records, or consultation payments. Keep secrets, patient data, verification documents, local mail, virtual environments, and backups out of Git.

## Repository and documentation

- [`backend/`](backend/) — Django API, domain services, Celery tasks, and tests.
- [`frontend/`](frontend/) — Next.js patient experience and role dashboards.
- [`compose.yml`](compose.yml) — Local PostgreSQL, Redis, and optional Ollama service.
- [Patient frontend](docs/patient-frontend.md), [role dashboards](docs/role-dashboards.md), [AI and support guide](docs/ai-assistant.md), and [AWS deployment](docs/aws-deployment.md) — implementation and operating notes.
