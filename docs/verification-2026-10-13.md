# Deployment preparation verification — 2026-10-13

Scope: local BYdoc source and production Docker image on branch `feat/otp-jwt-nearby-clinics`, before any cloud staging environment exists. These results do not establish public-launch readiness.

## Completed checks

| Check | Result |
| --- | --- |
| Python dependency audit | Initial DRF 3.16.1 and pytest 8.4.2 advisories addressed. Final `pip-audit -r backend/requirements/production.txt`: no known vulnerabilities. |
| Frontend dependency audit | `npm ci` and `npm audit`: 0 reported vulnerabilities. |
| Backend suite | 323 passed with pinned production dependencies and pytest 9.1.1, including trusted-proxy client-address tests. |
| Django model/schema checks | `makemigrations --check --dry-run`: no changes. `spectacular --validate --fail-on-warn`: passed. |
| Frontend checks | Typecheck, browser auth retry test, and production build passed. |
| Production container | Built on Python 3.12 slim Debian 13 (Trixie); `pip check` passed. Runs as uid 999 with Render secret-file group 1000. |
| Container vulnerability scan | Trivy 0.69.3: 0 critical, 44 high system-package findings without a fixed version reported by the scanner; 0 Python package findings. Fixable high/critical gate passed. The prior Debian 12 image had 2 critical and 57 high/critical system findings. |
| Tracked-file credential scan | No committed `.env` other than examples and no matches for selected common private-key/API-key patterns. This is a targeted scan, not a guarantee that every secret pattern is covered. |
| Production Django check | `check --deploy` passed except existing HSTS include-subdomains and preload warnings, which require domain ownership and verification before enabling. |

Docker Scout required a Docker account login, so the image scan used Trivy. Scanner results are advisory and depend on its vulnerability database and Debian status. CI now repeats Python, npm, and fixable image vulnerability checks.

## Cloud acceptance checks still pending

- Create Vercel, Render, and Supabase accounts; choose a domain and staging hostnames. None are available yet.
- Provision Supabase with verified TLS, authenticated TLS Redis, real SMTP delivery, Render API/worker/Beat, DNS, backups, monitoring, and a restore drill.
- Verify Render's trusted TLS/client-IP forwarding before enabling forwarded-header options or inviting users. The guarded `X-Forwarded-For` option needs this live check; without it, IP rate limiting may group users behind the Render proxy.
- Test secure cookie login, CSRF, OTP, role permissions, booking, cancellations, support, and job recovery on real HTTPS staging hosts.
- Complete accessibility, localization, clinical-safety, privacy, operational, and payment/SMS provider acceptance before public launch. Payments, SMS, and optional AI remain disabled until separately approved and verified.

See the [current staging runbook](vercel-render-supabase-deployment.md) for the ordered setup and release gates.
