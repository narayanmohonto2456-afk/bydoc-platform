# SehatSaathi Platform

SehatSaathi is a healthcare discovery and outpatient appointment project for patients, caregivers, clinics, and doctors. The name is provisional. Essential patient access is planned to be free; patients initially pay the provider's declared consultation fee directly to the provider.

## Current status

The Django backend has organization and clinic models, doctor profiles and verification data, appointment slots and race-safe booking, a notification outbox and inbox, support cases, preferences, patient accounts, verified email recovery, and a patient profile API. The Next.js frontend covers account registration, email or username sign-in, optional Google sign-in, email verification, password reset, profile editing, and patient discovery and booking.

The patient frontend now provides verified doctor and clinic discovery plus an online booking flow with live slots, a short hold, fee review, and server-confirmed appointment status. It does not yet provide patient notification or support screens, family-member booking, or a cancellation UI. Clinic staff workflows, full frontend translations, production email delivery, deployment, monitoring, and backup restoration still need work. This repository is **not production ready**.

An [AWS deployment design and release runbook](docs/aws-deployment.md) describes the proposed production environment, required secrets, container builds, release checks, and remaining launch gates. The backend has fail-closed production settings and a deployable container image; the frontend has a standalone container image. No AWS infrastructure has been provisioned from this repository.

The patient interface includes a [local AI guide](docs/ai-assistant.md) for account and app questions. It uses Ollama when enabled and keeps the model private. It cannot give medical advice or change bookings.

Signed-in users have [separate patient, doctor, clinic, and platform-admin dashboards](docs/role-dashboards.md). The current dashboards show role-scoped summaries; booking and clinic operations remain future work.

The latest frontend and sign-in work is on `feat/email-google-auth`, built on `feat/frontend-experience`. Those branches are pushed to GitHub but are not merged into `main`.

Next milestones are receptionist clinic operations, patient booking management and support, broader language and accessibility coverage, and launch hardening. The August 2026 planning drafts list phone OTP as a P0 requirement; the current app uses email/password with optional Google sign-in. That product decision needs to be reconciled before treating the original plan as complete.

## Local setup (Windows PowerShell)

Run these commands from the repository root unless a step changes directory. Install Python, Node.js, and Docker Desktop first. Docker Desktop must be running.

1. Create a local configuration file, set a development database password, and start PostgreSQL and Redis:

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

Open `http://localhost:3000`. Use `localhost` consistently in the browser so the development session cookie and CSRF flow work. The API is at `http://localhost:8000/api/v1/`; liveness and readiness endpoints are under `/health/`.

Email verification and password reset requests need a Celery worker and Beat to deliver their links. Development mail is written to `backend/local-email`. See [patient frontend setup](docs/patient-frontend.md) for the worker commands and [account recovery](docs/account-recovery.md) for delivery behavior.

Google sign-in is optional and stays in a setup state until a Google web client ID is configured in both the root `.env` (`GOOGLE_OAUTH_CLIENT_ID`) and `frontend/.env.local` (`NEXT_PUBLIC_GOOGLE_CLIENT_ID`). See [email and Google sign-in](docs/email-google-sign-in.md) for setup and account linking. Do not put a Google client secret in the frontend.

## Checks

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

Backend CI also compiles translation catalogs and validates the OpenAPI schema. The current translated backend messages do not represent a complete Bengali or Hindi interface.
Frontend CI typechecks and builds the standalone server with an example HTTPS API origin.

## Project boundaries

PostgreSQL is the source of truth for appointment state. A selected slot or sent notification must never be presented as a confirmed booking without an authoritative confirmed appointment. Clinic and patient data require scoped authorization.

The initial product is not a diagnosis, treatment, emergency, prescription, medical-record, or consultation-payment service. Keep secrets, patient data, verification documents, local mail, virtual environments, and database backups out of Git.

## Repository guide

- `backend/` — Django API, domain models and services, Celery workers, and tests.
- `frontend/` — Next.js patient account interface.
- `docs/` — Current implementation and setup notes.
- `compose.yml` — Local PostgreSQL and Redis services.
- `.github/workflows/` — Backend CI.
