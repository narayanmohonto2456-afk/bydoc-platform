# BYdoc

BYdoc is a healthcare discovery and outpatient appointment platform for patients, doctors, and clinics. Patients can find verified providers, review available slots and declared consultation fees, and receive a server-confirmed booking. The project includes separate role dashboards and an operational support flow.

> **Project status:** Active development. The repository is not ready for public production deployment. See [Deployment readiness](#deployment-readiness) for the remaining work.

## What works today

| Area | Current implementation |
| --- | --- |
| Patient accounts | Registration, password sign-in, one-time codes to a verified email or phone, optional Google sign-in, contact verification, password recovery, and profile editing. Browser API authentication uses short-lived JWT cookies and rotating refresh credentials. |
| Discovery and booking | Verified doctor and clinic discovery, a nearby clinic map with permission-based location access, live slots, short holds, fee review, and idempotent booking confirmation. PostgreSQL is the source of truth for appointment status. |
| Consultation payments | Optional Razorpay Route checkout after booking for enabled clinics, with server-verified capture, payment status, and full refunds after cancellation. Pay at clinic remains available. |
| Role dashboards | Separate patient, doctor, clinic, and platform operations workspaces with role-scoped data and actions. |
| Provider applications | Doctors and clinic representatives can submit registration details from an email-verified account. Independent admin review creates approved provider records; pending applications stay private. |
| Support | Guided help for app tasks, support request submission, case references and status, and staff case administration. Optional private AI classifies free-text topics; patients receive reviewed answers. |
| Backend operations | Scoped staff grants, provider review and suspension, payment and refund exception review, support assignment and escalation, appointment cancellation desk, delivery retry queue, immutable audit events, Celery jobs, and health checks. |

The frontend uses **Next.js**. The API and background jobs use **Django, Django REST Framework, and Celery**, with **PostgreSQL** for durable data and **Redis** for jobs and shared limits. Local development uses Docker Compose for PostgreSQL and Redis. The optional AI topic classifier uses a self-hosted Ollama service.

## Quick start (Windows PowerShell)

Prerequisites: Python 3.12, Node.js 22, and Docker Desktop. The commands below start from the repository root, with Docker Desktop running. These are the versions used in CI and the production image.

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

Online consultation payments are disabled by default. See the [Razorpay Route setup and refund runbook](docs/payments.md) before enabling them. Booking works with pay at clinic while payment credentials and linked clinic accounts are absent.

Doctors and clinics can apply through `/join`. See the [provider onboarding guide](docs/provider-onboarding.md) for verification and review steps. No identity documents are uploaded in this first version.

Superusers can assign scoped operations roles in `/dashboard/admin`. See the [admin operations guide](docs/admin-operations.md) for the review queues, required reasons, audit history, and limits of each action. Existing Django staff accounts need explicit grants after migration.

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

Production Python versions are fixed in [`backend/requirements/production.txt`](backend/requirements/production.txt), and the frontend uses `npm ci` from its lockfile. Both CI workflows check for known dependency vulnerabilities.

The latest [local predeployment verification record](docs/verification-2026-10-15.md) lists the test, dependency, browser, and production settings checks, plus the cloud checks still pending. The earlier [container preparation record](docs/verification-2026-10-13.md) includes image vulnerability results.

## Deployment readiness

For guided account creation and setup order, start with [your first staging deployment](docs/first-deployment-guide.md). Current verified results and remaining gates are recorded in [the readiness checklist](tasks/deployment-readiness.md).

The [Vercel, Render, and Supabase staging runbook](docs/vercel-render-supabase-deployment.md) is the current deployment path. The earlier [AWS deployment design](docs/aws-deployment.md) remains as a reference. Production settings and a container image exist, but no cloud accounts, domain, or deployed environment are configured yet. **Do not treat a passing build as approval to launch.** Remaining work includes:

- Provisioning and testing the production environment, HTTPS, email delivery, monitoring, backup restoration, and incident procedures.
- Completing clinic receptionist workflows, patient rescheduling, and patient notification screens.
- Reviewing accessibility and Bengali/Hindi coverage, plus clinical safety testing of the assistant before public healthcare use.
- Registering and validating the SMS sender and approved templates, configuring a Google web client ID, and choosing a managed map tile service for production traffic.
- Completing Razorpay merchant and Route onboarding, linked clinic accounts, live webhook delivery, refund and transfer testing, and finance reconciliation before enabling live payments.

PostgreSQL is authoritative for bookings: a selected slot, hold, or sent notification is not a confirmed appointment. BYdoc does not currently provide diagnosis, treatment, emergency care, prescriptions, or medical records. Keep secrets, patient data, verification documents, local mail, virtual environments, and backups out of Git.

## Repository and documentation

- [`backend/`](backend/) — Django API, domain services, Celery tasks, and tests.
- [`frontend/`](frontend/) — Next.js patient experience and role dashboards.
- [`compose.yml`](compose.yml) — Local PostgreSQL, Redis, and optional Ollama service.
- [Patient frontend](docs/patient-frontend.md), [role dashboards](docs/role-dashboards.md), [admin operations](docs/admin-operations.md), [AI and support guide](docs/ai-assistant.md), and [AWS deployment](docs/aws-deployment.md) — implementation and operating notes.
