# Patient authentication

The browser API uses Django's database-backed sessions. Public registration
creates an ordinary account and its default preferences. It does not grant
clinic membership, staff privileges or doctor status.

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/v1/auth/csrf/` | Set the CSRF cookie and return `csrf_token` |
| POST | `/api/v1/auth/register/` | Create an account; returns 201 |
| POST | `/api/v1/auth/login/` | Start a session; return user and rotated CSRF token |
| POST | `/api/v1/auth/logout/` | Invalidate the session; returns 204 |
| GET | `/api/v1/auth/me/` | Return the current account's public profile fields |

Registration accepts only `username`, `password`, and optional `first_name`
and `last_name`. Unrecognized fields are rejected. Django password validators
run with the candidate user, and passwords are hashed with `create_user`.
The API accepts passwords up to 128 characters and preserves whitespace.
Usernames are Unicode-normalized and case-sensitive.

Registration does not log the browser in. Call login after a successful
registration. Login takes `username` and `password`; invalid credentials,
missing users and inactive users return the same 400 response.

Account responses expose only `id`, `username`, `first_name` and `last_name`.
The account endpoint is read-only. It does not accept a target user ID.
Unauthenticated session-only endpoints return 403.

## Browser integration

1. Fetch `/api/v1/auth/csrf/` with `credentials: "include"`.
2. Keep its returned `csrf_token` in memory.
3. Send JSON mutations with `Content-Type: application/json`,
   `X-CSRFToken: <token>`, and `credentials: "include"`.
4. Replace the in-memory token with the new token returned by successful login.
5. Use the session cookie for subsequent API requests. Do not store passwords
   or session identifiers in browser storage.

All auth responses use `Cache-Control: no-store` and vary by cookie. Session
cookies are HttpOnly, SameSite=Lax, and expire after 12 hours. Basic
Authentication is removed from the default API authentication classes so it
cannot bypass login rate limits. Existing session-based language preferences
continue to apply on subsequent requests.

For local development use `localhost` consistently for frontend and backend;
do not mix it with `127.0.0.1` in browser URLs. Credentialed CORS is enabled only
for origins in `CORS_ALLOWED_ORIGINS`. CSRF origins are configured separately.

## Rate limits and Redis

The `authentication` cache uses the existing `REDIS_URL` with a dedicated key
prefix. Counter identities are hashed with Django's secret key. Windows,
scopes and limits are configured in `AUTH_RATE_LIMITS`:

- Login: 30 attempts per source address per minute.
- Login: 10 attempts per normalized username per five minutes, across addresses.
- Registration: 5 attempts per source address per hour.

These are fixed windows; traffic can burst around a window boundary. All
attempts reaching the limiter count, including successful logins. Exceeded
limits return 429 with `Retry-After`. Redis errors return a generic 503 and
block registration/login rather than disabling protection. Existing sessions
and logout do not depend on this Redis limiter.

`REMOTE_ADDR` is the source address. Forwarded headers are deliberately ignored.
Configure and verify trusted proxy address handling before deployment, or all
visitors behind one reverse proxy will share an address limit. Add edge-level
request limits as part of deployment protection.

## Verification and remaining launch work

Tests use a separate in-memory authentication cache and enforce CSRF checks.
Run the full test suite against PostgreSQL, and separately verify the real
Redis cache's `add`/`incr` connection. No migration is required by this module.

This is the username/password authentication milestone. Verified email/phone,
password recovery, and contact updates are not implemented here. Production
settings, HTTPS-only session/CSRF cookies, trusted proxy behavior, and staff
authentication controls must be completed before public launch. The existing
production settings file still needs implementation.

References: [DRF session authentication](https://www.django-rest-framework.org/api-guide/authentication/#sessionauthentication)
and [Django Redis caching](https://docs.djangoproject.com/en/5.2/topics/cache/#redis).
