# Verified email and account recovery

All routes use `/api/v1/auth/`. Browser writes require the CSRF token from `GET csrf/`.

- `POST email/verify/request/`: authenticated, `address` and `current_password`; returns 202. A verified address remains active until its replacement link is consumed. Requesting another verification link revokes earlier pending verification links.
- `POST email/verify/confirm/`: `token`; returns 204. The link expires after 30 minutes and is single use.
- `POST password/reset/request/`: `address`; returns the same 202 body whether an eligible account exists or not. Only verified email addresses qualify.
- `POST password/reset/confirm/`: `token` and `password`; returns 204. Password validation applies, and changing the password invalidates existing Django sessions and outstanding links.

The account link request is written to PostgreSQL before the API responds. Celery Beat dispatches pending email each minute and recovers abandoned attempts every five minutes. Workers retry failed sends up to five times. Claims recheck the retry time under a database lock, and a stale worker cannot finalize a newer attempt. A worker crash after provider acceptance can cause duplicate mail, while token consumption remains single use. Replacing a verified email invalidates outstanding reset links sent to the old address.

Local development writes messages to `backend/local-email` by default. Set `ACCOUNT_LINK_BASE_URL` to the frontend origin. The token is in the URL fragment so browsers do not send it to the frontend server in the HTTP request. Frontend verification and reset pages still need implementation. Production email delivery must be configured separately; no provider is enabled by this change.
