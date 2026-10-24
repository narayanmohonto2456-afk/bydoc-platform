# Deployment readiness

Target: Vercel frontend, Render API and Celery services, Supabase PostgreSQL.

- [x] Invalidate stale recovery links when verified email changes.
- [x] Invalidate issued OTP challenges on password reset.
- [x] Require an existing factor before enrolling an SMS sign-in number.
- [x] Apply shared authentication throttles to Django admin login.
- [x] Reconcile closed/reopened schedules without deleting bookings or reopening manual blocks.
- [x] Pass backend tests, schema and migration checks; frontend tests, typecheck and build.
- [x] Review dependencies and production deployment configuration.
- [x] Verify GitHub CI for the delivery branch.
- [ ] Create hosting projects and configure their secrets, database TLS and trusted origins.
- [ ] Configure and verify live email and SMS delivery.
- [ ] Deploy staging and verify authentication, booking, cancellation, payment/refund flows.

External setup: user confirmed on 2026-10-24 that hosting projects, a domain, and provider registrations have not yet been created. Guide account creation after the application checks. Do not store real credentials in this document or Git. Do not report staging or live provider checks as complete before they actually run.

## Verification on 2026-10-24

- Backend: 370 tests passed; schema validation and migration drift checks passed.
- Frontend: four authentication tests and the production build with TypeScript checks passed.
- Dependency audits: npm and the pinned production Python requirements reported no known vulnerabilities after upgrading Next.js to 16.4.3, Django REST Framework to 3.18.2, and certifi to 2026.10.19.
- Delivery commit `7457574`: [Frontend CI passed](https://github.com/narayanmohonto2456-afk/bydoc-platform/actions/runs/40073343917) and [Backend CI passed](https://github.com/narayanmohonto2456-afk/bydoc-platform/actions/runs/40073343985), including the production image build and fixable high/critical vulnerability scan.
- Production settings loaded with synthetic TLS endpoints. Django deployment checks reported only the two documented HSTS warnings: include-subdomains and preload remain disabled until ownership and HTTPS coverage of the actual domain are verified. Real database, Redis, SMTP, and proxy connectivity remain staging checks.
- Local migration `appointments.0005` applied without deleting bookings. No production migration or deployment has run.

Next owner step: follow [the first deployment guide](../docs/first-deployment-guide.md), beginning with account creation and multifactor authentication. Domain purchase, hosting charges, and provider approvals require owner participation. The delivery branch is `feat/appointment-booking`; `main` has not been merged.
