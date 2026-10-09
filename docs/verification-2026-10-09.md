# BYdoc verification — 9 October 2026

Branch: `feat/otp-jwt-nearby-clinics`

## Checks completed

| Area | Result |
| --- | --- |
| Backend tests | `python -m pytest --create-db -q`: **302 passed** against a fresh PostgreSQL test database. The suite covers accounts, Google token handling with mocks, OTP email and SMS delivery with mocks, JWT rotation and CSRF, appointments, nearby clinic queries, role dashboards, support, chatbot, notifications, preferences, translations, and production settings. |
| Backend checks | Django `check`, `makemigrations --check --dry-run`, and strict OpenAPI schema validation passed. `pip check` found no broken requirements. |
| Local database | Applied `accounts.0005_verifiedphone_authsession` and `accounts.0006_otpchallenge` successfully to the existing local PostgreSQL database. |
| Frontend | TypeScript typecheck and production build passed. HTTP smoke test covered all 14 page routes plus the expected 404 page; each returned the expected status and BYdoc branding. |
| Containers | Docker Compose configuration passed, including the optional AI profile. Backend and frontend release images built successfully. The backend image passed `manage.py check` at runtime; the frontend image served the tested routes. |
| Live local API | Health, readiness, CSRF, OTP availability, and public provider and nearby clinic discovery returned 200. Invalid coordinates returned 400. Protected account and appointment routes returned 401 without credentials. |

## Requires staging or provider access

- Google sign-in needs a configured Google web client ID and a permitted test account. Automated tests use mocked Google responses.
- SES email and AWS SMS need verified senders, approved SMS templates, credentials, and live delivery checks. Automated tests use the local mail backend and mocked SMS client.
- Browser automation was unavailable in this environment. The location permission prompt, map tile rendering, and full click-through flows need a browser check in staging over HTTPS.
- Production infrastructure, monitoring, backup restoration, and security review remain launch gates in [the AWS runbook](aws-deployment.md).
