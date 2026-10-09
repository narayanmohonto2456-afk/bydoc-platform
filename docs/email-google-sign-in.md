# Email and Google sign-in

Patient sign-in accepts a username or a **verified** email address with a password. New frontend registrations collect an email and queue a verification link. Until that link is confirmed, the patient can sign in with the username but not the email. Legacy username/password accounts continue to work.

Google sign-in uses [Google Identity Services](https://developers.google.com/identity/gsi/web/guides/display-button) in the browser. The backend checks the Google ID token signature, audience, issuer and expiry with `google-auth`, then identifies the Google account by its stable `sub` claim. The API sets an HttpOnly access JWT cookie and a rotating refresh cookie; browser writes still require the existing CSRF token. The app requests no Google API access or Google refresh token.

## Google setup

1. In Google Cloud Console, configure the OAuth consent screen and create a **Web application** OAuth client. Add `http://localhost:3000` as an authorized JavaScript origin for local testing. Add the deployed frontend origin when it is available. See Google's [web setup guide](https://developers.google.com/identity/gsi/web/guides/get-google-api-clientid).
2. Put the public client ID in the root `.env` as `GOOGLE_OAUTH_CLIENT_ID`. Put the **same** ID in `frontend/.env.local` as `NEXT_PUBLIC_GOOGLE_CLIENT_ID`. Restart Django and Next.js after changing the files. No Google client secret is needed for this Google Identity Services button flow.
3. Run `python manage.py migrate` from `backend` to create the Google identity table. Never commit `.env` or `.env.local`.
4. In local development, open `http://localhost:3000/login` or `/register` and use the Google button. The button stays in a setup state until the client ID is configured.

Google may require test users while the consent screen is in testing mode. For production, configure the real HTTPS origin and complete Google's publishing requirements before offering the button to patients. A live Google sign-in cannot be verified without a client ID and an allowed Google test account.

## Account behavior

- Google can create a new patient account with an unusable password. It never grants staff or superuser access.
- A Google email matching an existing account is **not** linked automatically. Sign in with that account's password, verify its email, then use **Connect Google** from My account.
- Linking requires an authenticated session, CSRF protection, and a Google credential for the account's already verified email.
- Google sign-in accepts Google verified Gmail and Google Workspace addresses. An external email on a Google account is not accepted because Google may no longer be authoritative for that mailbox. See Google's [ID token guidance](https://developers.google.com/identity/gsi/web/guides/verify-google-id-token).
- A Google-only account can set a password through the existing verified email reset flow. Existing password accounts can keep using username/password after connecting Google.

Email delivery uses the existing Celery worker and Beat described in [patient-frontend.md](patient-frontend.md). Local development writes messages to `backend/local-email`; configure a real email provider before production.
