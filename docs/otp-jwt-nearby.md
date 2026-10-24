# Authentication, delivery, and nearby clinics

BYdoc offers password sign-in, a one-time code to a verified email, and a one-time code to a verified phone. Google sign-in is available after a Google web client ID is configured. An account can verify its profile phone from the account page after signing in. A newly typed or changed phone cannot be used for SMS sign-in until verification succeeds.

## Browser authentication

The API sets an HttpOnly access JWT cookie (10 minutes) and an opaque rotating refresh cookie (30 days). The frontend refreshes on an expired access credential, then retries the request. Logout revokes the stored refresh session. Password changes invalidate credentials through the account authentication hash. Cookie-based unsafe requests require a CSRF token. Production cookies use Secure and `__Host-` names; Django admin keeps its separate staff session. The API also accepts a Bearer access JWT where a client already has one, but this release does not expose a mobile token issuance flow.

The sign-in routes live under `/api/v1/auth/`: `login/`, `google/`, `otp/status/`, `otp/request/`, `otp/confirm/`, `token/refresh/`, and `logout/`. Phone verification uses `phone/status/`, `phone/verify/request/`, and `phone/verify/confirm/`. OTP requests return a generic response for unknown contacts. Codes expire after 10 minutes, are single-use, allow five attempts, and are queued for Celery delivery. Start both the worker and Beat as shown in the README.

## Delivery and provider setup

### Local sign-in troubleshooting

Open the frontend at `http://localhost:3000` or `http://127.0.0.1:3000`. In development, API requests to a loopback address use the same hostname as the page so the browser can retain its authentication and CSRF cookies. The development backend permits those two exact frontend origins; production continues to use its explicitly configured origins.

If no code arrives, check the delivery path before retrying:

- Run both the Celery worker and Beat using the README commands. Starting Django, PostgreSQL, and Redis alone does not dispatch OTP messages.
- With the default file email backend, messages appear in `backend/local-email`, not in an inbox. The worker must be able to write to that directory. Live email requires the SMTP backend and provider settings.
- Email sign-in requires an already verified email. Sign in with a password and complete email verification from account settings first. A generic accepted response for an unknown or unverified address does not mean a code was created.
- SMS requires the configured sender, enabled SMS setting, and a verified phone. An unavailable SMS button reflects the backend's reported availability.

The local browser investigation verified email OTP request, worker delivery, code confirmation, and authentication after reload. Real email and SMS delivery still require provider configuration and separate live verification.

Local email codes are written to `backend/local-email`. Production uses the existing SES SMTP configuration: a verified sender identity, SMTP credentials, and production sending access. Test the full request, delivery, and confirmation flow in staging. [SES sender verification](https://docs.aws.amazon.com/ses/latest/dg/verify-addresses-and-domains.html) and [SMTP credential setup](https://docs.aws.amazon.com/ses/latest/dg/smtp-credentials.html) describe the AWS prerequisites.

SMS is off by default. Enable `OTP_SMS_ENABLED=true` only after setting `AWS_SMS_REGION`, `AWS_SMS_ORIGINATION_ID`, `AWS_SMS_ENTITY_ID`, `AWS_SMS_LOGIN_TEMPLATE_ID`, and `AWS_SMS_VERIFY_TEMPLATE_ID` in the API and worker. Grant their task role the required `sms-voice:SendTextMessage` permission. AWS End User Messaging SMS sends transactional messages through `SendTextMessage`. For India, register the sender and DLT entity and approve templates that match the actual login and phone-verification message bodies, including the code placeholder. Confirm real delivery before making the option available. See [AWS India sender requirements](https://docs.aws.amazon.com/sms-voice/latest/userguide/registrations-sms-senderid-india-specify-ids.html) and the [send API](https://boto3.amazonaws.com/v1/documentation/api/1.35.37/reference/services/pinpoint-sms-voice-v2/client/send_text_message.html).

Google sign-in requires the same public web client ID in backend `GOOGLE_OAUTH_CLIENT_ID` and frontend `NEXT_PUBLIC_GOOGLE_CLIENT_ID`. Register the frontend origin with Google. The backend verifies the Google ID token before creating or linking an account. A client secret does not belong in the browser. See [Google backend ID-token verification](https://developers.google.com/identity/sign-in/web/backend-auth).

## Nearby clinic map

The `/clinics/nearby` page asks for browser location only when the patient selects **Use my location**. It queries `/api/v1/appointments/nearby-clinics/` for active clinics within 15 km that have a verified doctor accepting online bookings. The API permits a 1–30 km radius, returns at most 50 distance-sorted clinics, and sends `Cache-Control: private, no-store`. Coordinates are used for the request and are not saved to the account. Patients can search by district without sharing location.

The map loads third-party tiles in the browser. `NEXT_PUBLIC_MAP_TILE_URL` and `NEXT_PUBLIC_MAP_ATTRIBUTION` are embedded at frontend build time, including in the production Docker build arguments. The example uses public OpenStreetMap tiles for development; choose a tile service with an appropriate production usage agreement and display its attribution. Review the [OpenStreetMap tile usage policy](https://operations.osmfoundation.org/policies/tiles/).

The displayed clinic distance is straight-line distance. Each clinic card and map marker offers **Get directions**, which opens Google Maps with the clinic coordinates as the destination. Google Maps chooses or asks for the starting point. This Maps URL needs neither BYdoc Google sign-in nor a Google Maps API key; routing stays in Google Maps.

## Release checks

Run migrations, the backend tests and schema validation, frontend typecheck and build, then verify password, email OTP, SMS verification and login, Google sign-in, token refresh, logout, and nearby discovery in staging. Use synthetic accounts and a real browser over HTTPS for cookie and geolocation checks. Keep SMS disabled until the AWS registration and sender test pass.
