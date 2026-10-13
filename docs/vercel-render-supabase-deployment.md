# BYdoc deployment: Vercel, Render, and Supabase

This is the proposed staging path. It does not create accounts, deploy services, or enable live payments. Use a separate staging database and test users. Public launch needs the release checks below.

## 1. Create the accounts and decide the hostnames

Create Vercel, Render, and Supabase projects using accounts you control, with multifactor authentication and billing alerts. Connect the GitHub repository with the minimum required repository access. Do not paste passwords, API keys, database URLs, or certificate contents into chat or Git.

Browser sign-in uses secure host-only JWT cookies and `SameSite=Lax`. The frontend and API must be HTTPS hosts on the **same registrable domain**, for example `app.your-domain.example` and `api.your-domain.example`. Vercel's `vercel.app` host and Render's `onrender.com` host cannot provide a reliable authenticated staging test with these cookie settings. The exact real domain and DNS records must come from the owner. Until then, the frontend and backend can be built separately, but authenticated browser acceptance testing is blocked.

Use separate staging and production hostnames, secrets, databases, and providers. Restrict staging access to testers; never copy real patient records into it.

## 2. Supabase PostgreSQL

Create a PostgreSQL project in a region near the Render service. In the Supabase **Connect** panel, copy the actual host, port, database, and username into Render secrets. If the direct connection is unavailable from Render because of IPv4, use the **session pooler** on port 5432. Do not use transaction mode until the application's connection behavior is tested with it.

In Supabase database SSL settings, turn on SSL enforcement and download that project's root certificate. Upload it to **each Render Docker service** as a runtime secret file named `supabase-ca.pem`; set `POSTGRES_SSLROOTCERT=/etc/secrets/supabase-ca.pem`. Production Django settings require certificate and hostname verification (`verify-full`). Test the chosen pooler hostname against the certificate before proceeding. The certificate is public material, but keeping the per-project file in Render avoids mixing it with the bundled AWS RDS certificate.

Create a database backup and perform a test restore into another database before inviting users. Record the recovery owner and the restore steps privately. Run `python manage.py migrate --noinput` once as a controlled pre-deploy action for the API; do not run simultaneous migrations from web, worker, and Beat.

## 3. Redis and Render services

Provision a Redis-compatible service with persistence appropriate for queued work and **authenticated TLS**. The current production settings require a `rediss://` URL with a password and `?ssl_cert_reqs=required`. Render Key Value's default internal URL is plaintext and unauthenticated, so it does not meet this requirement. Its TLS external URL can be used only after restricting external access to known Render outbound IPs, or use another managed TLS Redis service. Do not weaken the production Redis validation to make the default URL pass.

Create three Render Docker services from the repository, all with Docker context `backend` and Dockerfile `backend/Dockerfile`, in the same region:

| Service | Type | Start command | Purpose |
| --- | --- | --- | --- |
| API | Web service | Dockerfile default (`gunicorn ... --bind 0.0.0.0:8000`) | HTTPS API and admin |
| Worker | Background worker | `celery -A config worker --loglevel=INFO --concurrency=2` | Email, notification, payment, and recovery jobs |
| Beat | Background worker, one instance | `celery -A config beat --loglevel=INFO --schedule /tmp/bydoc-celerybeat-schedule` | Periodic dispatch and reconciliation |

Set API `PORT=8000` and health check path `/health/ready/`. The readiness endpoint checks dependencies and returns no private data. Keep the Beat instance count at one to avoid duplicate schedules. Give workers enough memory for their workload and set restart/alert policies in Render. The Docker image runs as a non-root user that can read Render's runtime secret files through group 1000.

Configure these variables on all three services using Render's environment settings or a private environment group. Generate a unique long `DJANGO_SECRET_KEY` for each environment; never reuse the local `.env` value:

| Variable | Value source |
| --- | --- |
| `DJANGO_SETTINGS_MODULE` | `config.settings.production` |
| `DJANGO_SECRET_KEY` | Private random secret, at least 50 characters |
| `APP_ALLOWED_HOSTS` | Exact API hostname; no scheme, wildcard, or port |
| `CORS_ALLOWED_ORIGINS` | Exact HTTPS frontend origin |
| `CSRF_TRUSTED_ORIGINS` | Exact HTTPS frontend origin |
| `ACCOUNT_LINK_BASE_URL` | Same HTTPS frontend origin |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT` | Supabase Connect panel |
| `POSTGRES_SSLROOTCERT` | `/etc/secrets/supabase-ca.pem` |
| `REDIS_URL` | Private authenticated TLS URL, with `ssl_cert_reqs=required` |
| `EMAIL_BACKEND` | `django.core.mail.backends.smtp.EmailBackend` |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | Transactional email provider |
| `EMAIL_USE_TLS`, `EMAIL_USE_SSL` | Exactly one `True`, matching provider port |
| `DEFAULT_FROM_EMAIL` | Verified sender on the owned domain |
| `TRUSTED_PROXY_SSL_HEADER` | Set `True` only after verifying Render overwrites client-supplied `X-Forwarded-Proto` at the edge |
| `TRUSTED_PROXY_CLIENT_IP` | Set `True` only after verifying Render sets the first `X-Forwarded-For` address to the actual client, even if the request supplied one |
| `OTP_SMS_ENABLED`, `RAZORPAY_PAYMENTS_ENABLED`, `AI_CHAT_ENABLED` | `False` until each integration has passed staging checks |

The production settings fail at startup when required values are missing. Do not commit Render secret exports or use the development email file backend in production. Configure a real email provider and verify delivery, bounce handling, and sender authentication before enabling account registration.

The authentication limiter defaults to `REMOTE_ADDR`. Behind Render's proxy that may be a shared proxy address. A validated `X-Forwarded-For` first-address option is implemented but disabled by default. Before inviting testers, verify Render's actual forwarding behavior with non-sensitive requests, including a request that supplies a fake header. Enable `TRUSTED_PROXY_CLIENT_IP=True` only when the edge replaces that first address with the real client. Until then, rate limits may affect unrelated users.

## 4. Vercel frontend

Import the same GitHub repository into Vercel. Set project root directory to `frontend`, framework to Next.js, and deploy the intended staging branch. Set `NEXT_PUBLIC_API_BASE_URL=https://<api-host>/api/v1` and `NEXT_PUBLIC_APP_NAME=BYdoc`. Only set `NEXT_PUBLIC_GOOGLE_CLIENT_ID` after creating a Google OAuth web client with the real frontend origins. Variables beginning `NEXT_PUBLIC_` are visible in browser builds; never put secrets there. Redeploy after changing a build-time variable.

Attach the owned staging frontend hostname to Vercel and API hostname to Render. Configure DNS and verify both certificates before testing sign-in. Add only those exact origins and hostnames to Django's allowlists. Disable unnecessary Vercel preview deployments for flows that need production cookies, or give previews their own controlled API and database environment.

## 5. Staging acceptance and release gate

1. Confirm CI is green, the image builds, `python manage.py check --deploy` has no new security warnings, and all migrations apply on the staging database.
2. Confirm `GET /health/ready/` succeeds through Render HTTPS, while API and admin requests use HTTPS without redirect loops. Verify real client IP handling and that spoofed forwarded headers cannot change the chosen client address.
3. Confirm frontend to API CORS, CSRF, secure cookies, login, refresh, logout, email OTP, password recovery, and role permissions on the real staging hostnames.
4. Test doctor/clinic applications, admin approval, discovery/map, slot hold/booking/cancellation, notifications, support cases, and worker/Beat recovery after restart.
5. Confirm database backups and a restore, Redis recovery, log redaction, alerts, and a rollback to the previous image/commit. Avoid recording patient data in logs.
6. Keep SMS, Google OAuth, optional AI classification, and Razorpay disabled until their provider accounts, approvals, callbacks, legal terms, and failure/refund flows have been verified separately.
7. Review accessibility, Bengali/Hindi text, clinical safety wording, privacy policy, consent, and operational support before any public healthcare launch.

For a release, deploy the backend image and migrations first, confirm readiness, then deploy the frontend build pointing at that API. Watch errors and queue depth. A code rollback does not reverse database migrations or already sent messages, so review schema changes and take a restorable backup before every release.

## Dependency upkeep

`backend/requirements/base.txt` declares supported direct dependency ranges; `backend/requirements/production.txt` records the exact Python 3.12 packages deployed in Docker and used by development/CI. Review and regenerate the production list on a Python 3.12 Linux environment when upgrading, then run `pip-audit`, `pip check`, backend tests, schema checks, and a fresh Docker build. `frontend/package-lock.json` is installed with `npm ci`; CI runs `npm audit --audit-level=high`.

## Provider references

- [Supabase connection modes and certificate verification](https://supabase.com/docs/guides/database/connecting-to-postgres)
- [Render Key Value connection security](https://render.com/docs/key-value)
- [Render Docker runtime secret files](https://render.com/docs/docker-secrets)
- [Render web health checks](https://render.com/docs/health-checks)
- [Vercel monorepo setup](https://vercel.com/docs/monorepos)
