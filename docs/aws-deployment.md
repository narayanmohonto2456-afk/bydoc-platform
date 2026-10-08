# AWS deployment design and release runbook

This is the target deployment for the current BYdoc code. It is a release plan, not evidence that AWS infrastructure or a production environment already exists. Choose the AWS Region and public domains before provisioning.

## Architecture

```text
Browser
  -> Route 53 + ACM HTTPS certificate + AWS WAF
  -> public Application Load Balancer (HTTP redirects to HTTPS)
       app.example.com -> ECS Fargate Next.js web service :3000
       api.example.com -> ECS Fargate Django API service :8000
  -> private ECS subnets: API, web, Celery worker, one Celery Beat task
       -> private RDS PostgreSQL (Multi-AZ, encrypted, TLS)
       -> private ElastiCache Redis OSS (encrypted in transit and at rest, AUTH)
       -> Amazon SES SMTP (verified sender domain)
```

Use at least two Availability Zones. Put only the load balancer in public subnets. ECS tasks, RDS, and Redis stay in private subnets; security groups allow only the required paths (ALB to web/API, application tasks to RDS/Redis, worker to SES). Give ECS task execution and application roles separate, least-privilege policies. Send container logs to CloudWatch with restricted access and retention. Use ECR repositories with image scanning, immutable tags, and lifecycle rules. Store runtime secrets in Secrets Manager, with KMS encryption and controlled rotation. ECS injects secrets into task environment at startup, so a secret rotation requires a new deployment of affected tasks.

The API image serves Django static assets through WhiteNoise. The web image is a Next.js standalone server. Run the same API image as four separate ECS task definitions or commands: API (default Gunicorn command), worker (`celery -A config worker --loglevel=INFO`), Beat (`celery -A config beat --loglevel=INFO`), and one-off migration (`python manage.py migrate --noinput`). Run exactly one Beat task. Give web and API services at least two tasks across zones after launch; scale workers from queue/latency metrics. Never run migrations as an automatic command in every API replica.

## Build and configuration

Build images from the repository root and push immutable image tags to ECR. The public API URL and optional Google web client ID are embedded in the web build, so rebuild the web image when either changes.

```sh
docker build -f backend/Dockerfile -t bydoc-api:RELEASE_SHA backend
docker build -f frontend/Dockerfile \
  --build-arg NEXT_PUBLIC_API_BASE_URL=https://api.example.com/api/v1 \
  --build-arg NEXT_PUBLIC_GOOGLE_CLIENT_ID=YOUR_PUBLIC_CLIENT_ID \
  -t bydoc-web:RELEASE_SHA frontend
```

Set `DJANGO_SETTINGS_MODULE=config.settings.production` on the API, worker, Beat, and migration tasks. The API image sets this by default. Set these environment values in the ECS task definition, replacing example domains:

| Setting | Source and value |
| --- | --- |
| `DJANGO_SECRET_KEY` | Secrets Manager; unique random value of at least 50 characters. Plan key rotation separately because changing it invalidates existing sessions and signed values. |
| `APP_ALLOWED_HOSTS` | `api.example.com`; exact API hostnames, comma separated. |
| `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS` | `https://app.example.com`; comma separated HTTPS origins. |
| `ACCOUNT_LINK_BASE_URL` | `https://app.example.com`; verification and recovery links. |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_HOST`, `POSTGRES_PORT` | RDS database, application user, endpoint, and `5432`. |
| `POSTGRES_PASSWORD` | Secrets Manager; dedicated database application user password. |
| `POSTGRES_SSLROOTCERT` | `/app/backend/certs/rds-global-bundle.pem`; public AWS RDS CA bundle included in the API image. |
| `REDIS_URL` | Secrets Manager; `rediss://:PASSWORD@REDIS_ENDPOINT:6379/0?ssl_cert_reqs=required`. URL-encode reserved password characters. |
| `EMAIL_BACKEND` | `django.core.mail.backends.smtp.EmailBackend`. |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS` | SES SMTP endpoint for the chosen Region, `587`, `True`. |
| `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | SES SMTP credentials from Secrets Manager. |
| `DEFAULT_FROM_EMAIL` | Verified sender, e.g. `BYdoc <no-reply@example.com>`. |
| `TRUSTED_PROXY_SSL_HEADER` | `True` only when the ALB is the sole inbound path to the API and its `X-Forwarded-Proto` behavior has been verified against a spoofed client header. |
| `GOOGLE_OAUTH_CLIENT_ID` | Optional public Google web client ID, matching the web build. Configure authorized origins in Google Cloud. |

Do not set `APP_DEBUG=True` in production. The production module forces `DEBUG=False`, checks required values at startup, requires verified TLS for PostgreSQL and authenticated TLS for Redis, and rejects development email delivery. It does not load the repository `.env` file. Keep RDS and Redis endpoints on private DNS names whose certificates match the TLS hostnames. The included RDS CA bundle is a public trust anchor; refresh it on AWS CA rotation and rebuild the image. Django's deployment check intentionally warns that HSTS does not include all subdomains and is not preloaded; enable those policies only after verifying every subdomain is HTTPS-only and you control the full domain.

The AWS ALB checks `GET /health/ready/` on the API target group and `GET /` on the web target group. The API health middleware answers its two exact health GET paths before Django's public Host and HTTPS checks because ALB target checks use a private IP Host over HTTP. Readiness returns only a generic status and checks PostgreSQL and Redis. Other API requests still enforce the public Host and HTTPS policy. Set target health timeout to allow the dependency checks; use a separate synthetic HTTPS check through the public domain to verify the full edge path. Confirm the ALB's HTTP listener redirects to HTTPS and that API security headers and cookies are present on public responses.

## Release sequence

1. Provision Route 53, ACM, WAF, VPC/subnets/security groups, ECR, Secrets Manager, RDS, Redis, SES, CloudWatch, ECS, and the ALB using reviewed infrastructure as code. Turn on RDS automated backups, point-in-time recovery, deletion protection, and Multi-AZ. Verify SES production sending and domain authentication (SPF, DKIM, DMARC).
2. Build and scan the images in CI. Push images to ECR with the commit SHA; deploy a staging environment from those exact image digests. Run backend tests, frontend typecheck/build, `python manage.py check --deploy` (review the two deliberate HSTS warnings), and a test account flow in staging.
3. Take a verified pre-release RDS recovery point. Run the one-off migration task once, wait for success, then update the worker, Beat, API, and web services to the new image digests. Confirm ALB target health and one Beat instance.
4. Smoke-test HTTPS, registration, email verification, sign-in, password reset, Google sign-in if configured, CSRF, booking concurrency, notification delivery, and tenant permissions with synthetic accounts only. Confirm failed login throttling and no secrets or patient data in logs.
5. Monitor 5xx rate, p95 latency, unhealthy targets, task restarts, RDS storage/connections, Redis memory, Celery queue age and failures, SES bounces, and backup status. Page the on-call owner for critical failures. Rehearse restoring RDS into an isolated environment and record recovery time and recovery point. Test rollback using previous image digests; reverse incompatible migrations through a forward fix or a documented database restore.

## Launch gates still open

The guided help and support-request chat is enabled by default through `ASSISTANT_ENABLED=true` and uses the existing support database and API. The optional AI topic classifier is disabled by default and needs a separately operated private Ollama service and model volume. To enable it, set `AI_CHAT_ENABLED=true`, `OLLAMA_BASE_URL=http://ollama.service.internal:11434`, and `OLLAMA_MODEL=llama3.2:3b` on the API tasks. Allow network access only from the API tasks, review model capacity and logs, and complete the clinical safety review described in [the AI guide](ai-assistant.md). If the model fails, reviewed product guidance continues. This self-hosted model has no usage-based API fee but consumes AWS compute and storage.

- Production infrastructure as code, AWS account/Region/domains, budgets, IAM review, key rotation, and alert routing have not been configured in this repository.
- Staff and administrator MFA, a permissions audit across patient and clinic endpoints, and an independent security review are required before handling real patient information. Google sign-in remains optional until a client ID is configured.
- Patient booking management and clinic operations are still incomplete. The historical product plan's phone OTP requirement conflicts with the current email/Google authentication choice and needs a product decision.
- File uploads and verification documents must use a private, encrypted object store with access controls and malware scanning before they are enabled. The current container filesystem is ephemeral.
- Complete a staging restore drill, load/concurrency test, accessibility review, and incident response rehearsal before public launch.

Do not treat a successful container build or Django deployment check as approval to use the service with real patient data.
