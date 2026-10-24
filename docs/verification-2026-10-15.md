# Local predeployment verification — 2026-10-15

Scope: `feat/admin-operations` on the local development stack. This is a regression and browser smoke check, not acceptance of a deployed production environment.

| Check | Result |
| --- | --- |
| Services | Existing PostgreSQL and Redis Compose containers healthy; Django on `localhost:8000` and Next.js on `localhost:3000` returned HTTP 200. No Docker volumes were reset. |
| Backend | 332 tests passed; Django `check`, migration drift check, and OpenAPI validation passed. Pytest emitted only a local cache write warning from the workspace sandbox. |
| Frontend | Typecheck, auth retry test, and production build passed. |
| Dependencies | `pip check` passed; `pip-audit` on production requirements found no known vulnerabilities; `npm audit --audit-level=high` reported 0 vulnerabilities. |
| Chrome DevTools | Password sign-in, seven admin queue tabs, staff account search and grant confirmation, appointment reference validation, provider forms, account settings, appointment empty state, geolocation clinic map and empty state, chatbot guidance, and the public home page were checked. No console errors or warnings were found. Desktop and narrow viewport layouts were inspected. |
| Production configuration | `check --deploy` loaded production settings with placeholder TLS services and credentials. It reported the intentional HSTS subdomain and preload warnings; the placeholder secret also triggered the weak-secret warning. This does not test real production connectivity. |

The browser pass found two admin usability issues. Staff grants now use a bounded username/email account search instead of requiring a copied UUID; the admin tabs now wrap on desktop so Audit history is visible. The related API permission test passed and the full suite was rerun. Temporary browser QA accounts were deleted after the check.

## Still required before launch

- Create and test the Vercel, Render, and Supabase staging services, domain, HTTPS, Redis TLS, SMTP delivery, monitoring, backups, and restore procedure.
- Recheck auth cookies, CSRF, email OTP, provider review, booking, cancellations, notifications, and support end to end on staging with representative data. The local database has no active clinics or verified bookable doctors, so the browser could only verify their empty states. API tests cover the state-changing flows.
- Configure and separately accept Google OAuth, SMS delivery, Razorpay Route, live webhook/refund settlement, and any production map tile provider. Those integrations are not configured locally and were not live-tested.
- Review accessibility, localization, and clinical safety before public healthcare use.

See the [staging runbook](vercel-render-supabase-deployment.md) for the deployment sequence and gates.
