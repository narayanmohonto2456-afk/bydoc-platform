# Patient account frontend

This Next.js application implements registration, email or username sign-in, configurable Google sign-in, patient profile editing, verified email request/confirmation, password reset, and doctor discovery with appointment booking. It uses the existing Django session and CSRF APIs. See [email-google-sign-in.md](email-google-sign-in.md) for Google setup and account linking. It does not yet provide patient notification or support screens, family-member booking, a cancellation UI, or full Bengali and Hindi interface translations.

The `/appointments` page searches active clinics and doctors with current verified registrations. Patients can view open slots, review the declared fee, hold a slot for a short period, and confirm a booking. The page shows confirmed status only from the booking API response. If confirmation is interrupted, it retains the same booking request ID for an idempotent retry. The backend checks doctor verification at slot lookup and again when holding or booking. Payments are made directly to the clinic.

## Local setup on Windows

From the repository root, start PostgreSQL and Redis:

```powershell
cd E:\start_up\bydoc-platform
docker compose up -d postgres redis
```

From `backend`, run Django:

```powershell
cd E:\start_up\bydoc-platform\backend
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements/development.txt
.\venv\Scripts\python.exe manage.py migrate
.\venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

From `frontend`, install dependencies and start Next.js in another terminal:

```powershell
cd E:\start_up\bydoc-platform\frontend
Copy-Item .env.example .env.local
npm.cmd ci
npm.cmd run dev
```

Open `http://localhost:3000`. Use `localhost` consistently for both frontend and backend so browser cookies work in this local setup. The backend must allow `http://localhost:3000` in its CORS and CSRF trusted origins. Set `NEXT_PUBLIC_API_BASE_URL` for any different backend origin.

Email requests are stored in PostgreSQL. To deliver local verification or reset links, run a Celery worker and Beat in separate backend terminals. Development mail is written under `backend/local-email` by default. Production email, HTTPS, and cookie settings require deployment configuration.

```powershell
cd E:\start_up\bydoc-platform\backend
.\venv\Scripts\python.exe -m celery -A config worker --loglevel=INFO --pool=solo --concurrency=1 --without-mingle --without-gossip
```

Run Beat separately from `backend`:

```powershell
.\venv\Scripts\python.exe -m celery -A config beat --loglevel=INFO --schedule "$env:TEMP\bydoc-celerybeat-schedule"
```

## Checks

From `frontend`:

```powershell
npm.cmd run typecheck
npm.cmd run build
```

The frontend never sends a patient ID with profile updates. Session cookies remain HttpOnly; unsafe API requests fetch a fresh CSRF token and send it in `X-CSRFToken`. Verification and reset tokens are read from URL fragments and removed from browser history when their pages load.

The home page offers an interactive account setup guide. Keyboard users can move between its tabs with the left and right arrow keys. Forms show password visibility and strength feedback, and profile editing shows unsaved changes with a discard action. Motion respects the operating system's reduced motion preference.
