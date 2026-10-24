# Deployment readiness

Target: Vercel frontend, Render API and Celery services, Supabase PostgreSQL.

- [x] Invalidate stale recovery links when verified email changes.
- [x] Invalidate issued OTP challenges on password reset.
- [x] Require an existing factor before enrolling an SMS sign-in number.
- [x] Apply shared authentication throttles to Django admin login.
- [x] Reconcile closed/reopened schedules without deleting bookings or reopening manual blocks.
- [ ] Pass backend tests, schema and migration checks; frontend tests, typecheck and build.
- [ ] Review dependencies and production deployment configuration.
- [ ] Verify GitHub CI for the delivery branch.
- [ ] Create hosting projects and configure their secrets, database TLS and trusted origins.
- [ ] Configure and verify live email and SMS delivery.
- [ ] Deploy staging and verify authentication, booking, cancellation, payment/refund flows.

External setup: user confirmed on 2026-10-24 that hosting projects, a domain, and provider registrations have not yet been created. Guide account creation after the application checks. Do not store real credentials in this document or Git. Do not report staging or live provider checks as complete before they actually run.
