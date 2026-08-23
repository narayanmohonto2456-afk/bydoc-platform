# SehatSaathi Platform

SehatSaathi is a multilingual, low-data healthcare discovery and outpatient appointment platform for patients, caregivers, clinics, doctors, and authorized community agents.

> SehatSaathi is a working name. Branding must remain configurable and separate from appointment, identity, clinic, verification, and permission logic.

## Current status

Production development foundation is in progress.

The existing UI is a concept prototype. It is not connected to production authentication, PostgreSQL, clinic authorization, provider verification, notifications, or appointment concurrency controls.

## Project priorities

When decisions conflict, follow this order:

1. Patient safety and applicable law
2. Privacy and security
3. Appointment and data integrity
4. Approved product requirements
5. Approved architecture
6. Project rules
7. Delivery and design convenience

## Initial technology

- Python and Django
- Django REST Framework
- PostgreSQL
- Redis and Celery
- Next.js and React
- Docker
- Reverse proxy, load balancer, and API gateway
- Private object storage

## Repository structure

- `backend/` — Django, DRF, domain services and background workers
- `frontend/` — Next.js patient and clinic applications
- `infrastructure/` — Docker, proxy and deployment configuration
- `docs/` — Product and technical documentation
- `scripts/` — Development and operational scripts
- `.github/workflows/` — Automated checks

## Initial business model

Essential patient access is free during the initial launch.

Patients initially pay only the provider's declared consultation fee directly to the provider. SehatSaathi does not initially collect the consultation payment.

## Product boundary

The MVP is not:

- A diagnosis system
- A treatment recommendation system
- An emergency service
- A prescription or medical-record system
- An insurance, pharmacy or laboratory platform

## Security

Never commit:

- `.env` files
- Passwords or API keys
- OTP values
- Patient or clinic production data
- Verification documents
- Database backups

Use `.env.example` only as a safe configuration template.