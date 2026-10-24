# BYdoc: your first staging deployment

This guide connects the existing application to Vercel, Render, and Supabase. Complete one stage at a time. Account creation, domain ownership, provider approval, and billing decisions need the owner's participation. Keep passwords, API keys, SMTP credentials, and database URLs in a password manager or hosting secrets, never in chat or Git.

## 1. Create your hosting logins

Create accounts at [Supabase](https://supabase.com/dashboard), [Render](https://dashboard.render.com/), and [Vercel](https://vercel.com/signup). Enable multifactor authentication. Connect your GitHub account, granting access to `narayanmohonto2456-afk/bydoc-platform` only where possible. Review displayed charges before creating services or choosing paid plans.

At this first stage, share only that the accounts exist. Credentials are not needed in chat. We will create the staging database before deploying either application.

## 2. Choose a domain you control

Choose and register your actual domain, then keep access to its DNS settings. With the existing secure cookie policy, frontend and API need HTTPS hostnames on the same registrable domain. Reserve separate frontend and API subdomains for staging, and separate ones for production. The exact names will use your real domain; do not copy placeholder domains into configuration.

The default Vercel and Render hostnames are on different sites and do not provide reliable authenticated browser testing with our `SameSite=Lax` cookies. Do not solve that by disabling cookie or CSRF security.

## 3. Create the staging database

In Supabase, create a project for BYdoc staging and choose a region near the backend. Save the database password privately. In **Connect**, obtain the database connection parameters; use the session pooler if the direct host is not reachable over IPv4. Turn on SSL enforcement and download the project's database CA certificate. The app uses Django authentication; no Supabase browser authentication keys are needed.

Put database parameters into Render's secret environment settings and the CA certificate into its runtime secret file. Follow the exact variable table in [the deployment configuration](vercel-render-supabase-deployment.md). Test `verify-full` TLS before running migrations. Use synthetic accounts in staging, and verify backup/restore before public use.

Official references: [connection options](https://supabase.com/docs/guides/database/connecting-to-postgres), [SSL enforcement](https://supabase.com/docs/guides/platform/ssl-enforcement).

## 4. Create the backend services

Create a Render web service for the API, a background worker for Celery, and one background worker for Beat. Use Docker context `backend` and the commands in [the deployment configuration](vercel-render-supabase-deployment.md). Add an authenticated TLS Redis service; PostgreSQL alone does not handle the task queue or shared login limits.

Configure production environment variables and secrets on all three services. Run migrations once as the API's controlled pre-deploy action. Set readiness to `/health/ready/`. Attach the real staging API hostname and verify HTTPS. Verify forwarded client IP and HTTPS headers before enabling either trusted-proxy option.

Initially keep automatic deployment off. After the first manual staging check, choose **After CI Checks Pass** on the API and worker services. Keep Beat at one instance. Official reference: [Render deployment controls](https://render.com/docs/deploys).

## 5. Enable real email, then SMS

For Amazon SES, verify your sender/domain, configure the required DNS records, create SMTP credentials, and obtain production sending access before sending to arbitrary users. Add those SMTP settings privately to Render. Test registration verification, email OTP, and password recovery on a mailbox you own.

For AWS SMS to India, complete sender and DLT entity/template registration, configure both approved templates and the AWS runtime credentials/permissions, then verify delivery to a consenting test phone. Enable `OTP_SMS_ENABLED` only for that check and after approval. SMS enrollment requires an existing password; a Google-only user can create one through verified email recovery.

Provider approval can take time, so it cannot be guaranteed to fit a two-day launch. Keep incomplete integrations disabled. Official references: [SES production access](https://docs.aws.amazon.com/ses/latest/dg/request-production-access.html), [India SMS registration](https://docs.aws.amazon.com/sms-voice/latest/userguide/registrations-sms-senderid-india-support.html).

## 6. Deploy the frontend

Import the same repository into Vercel with root directory `frontend` and framework Next.js. Point `NEXT_PUBLIC_API_BASE_URL` at the real staging API URL ending in `/api/v1`. Attach the staging frontend hostname and add its exact HTTPS origin to the backend's CORS and CSRF settings. Redeploy after changing public build variables. Keep provider secrets out of `NEXT_PUBLIC_` variables.

Use the feature/staging branch for acceptance testing. Production promotion remains an explicit reviewed action after CI passes. Official reference: [Vercel project setup](https://vercel.com/docs/projects/managing-projects).

## 7. Complete acceptance before public launch

Verify password and email OTP login, session refresh/logout, recovery and phone enrollment protections; provider applications and approvals; nearby clinic map/directions; slot hold, booking and cancellation; support; notifications; and worker recovery. Use Razorpay test credentials to verify payment capture, duplicate callbacks, cancellation, full refund, and delayed webhook delivery. No real patient payments are needed for these checks.

Verify alerts, restricted logs, database restore, and rollback to the previous image. Record each actual result in [the readiness checklist](../tasks/deployment-readiness.md). Only promote to production after these checks pass and the owner approves the release.
