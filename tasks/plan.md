# Implementation Plan: BYdoc appointment booking

Status: implementation in progress on feat/appointment-booking (2026-10-24).

## Goal and scope

Deliver a pilot-ready outpatient booking journey: clinic staff publish trustworthy schedules; a patient finds a verified doctor, holds and confirms one slot, sees the authoritative result, and can cancel or reschedule; authorized clinic staff can manage the same schedule and bookings. Keep optional Razorpay payment after confirmation and full refunds on cancellation. Family and community-agent booking are a separate follow-on milestone because consent and patient identity need a distinct design.

## Current baseline

- Implemented: verified provider search, public slot lookup, five-minute server holds, PostgreSQL row-locked and idempotent confirmation, patient appointment list, cancellation API, notification outbox, optional post-booking payment, and a read-only clinic dashboard.
- Gaps: schedule rules/slot generation are admin or service driven; no clinic schedule editor or automated publication path; no durable booking request lookup after a lost response; no patient cancellation or rescheduling screen; no reschedule command; no clinic receptionist booking or visit-state commands.
- Integrity gap to resolve first: appointment responses and new payment orders read the affiliation's current consultation fee rather than a booking-time snapshot. A later fee edit could change the apparent price of an existing appointment.
- Existing tests cover the normal hold/book/cancel path, duplicate requests, rebooking a cancelled slot, and payment refunds. The full concurrent final-slot and reschedule races still need dedicated PostgreSQL verification.

## Architecture decisions

1. PostgreSQL remains the only authority for slot and appointment state. Reuse the existing row locks, unique constraints, and booking request IDs. A browser selection, expired hold, payment callback, or notification never confirms an appointment.
2. Keep the current immediate confirmation contract. Use submitting/uncertain/conflict as client states; add a persisted status only if an actual clinic approval workflow is introduced. Define one status/event contract before rescheduling so dashboards, payments, notifications, and support agree.
3. Snapshot fee and currency when the booking commits. Payment orders, confirmations, and history use this snapshot. A fee change affects future bookings only.
4. Clinic schedule writes and receptionist actions require an active, clinic-scoped grant. Organization owners/managers may manage their organization's clinics; receptionists receive explicit clinic assignments. All sensitive transitions record actor, time, and reason.
5. Reschedule atomically: acquire a new valid hold, lock the appointment and both slots in a consistent order, move the appointment, then release the old slot. Initially permit the same doctor and clinic at the same fee; a changed fee/provider uses cancellation, the existing full-refund path, and a new booking. This proposed rule needs product approval.
6. Preserve an appointment's identity and an append-only change history across rescheduling. Keep its payment state separate from appointment state. Rebuild reminder intents and issue a change notice only after the committed transition.
7. Avoid adding family members or agent-created patient records until identity, authorization, consent, and data-minimization rules are agreed.

## Delivery order

The detailed checklist is in [todo.md](todo.md). Each task should land as a small, testable slice.

### Milestone A: trustworthy inventory and price
Tasks 1-6: price snapshot, payment alignment, clinic access, schedule commands, schedule publication, and clinic editor.

### Checkpoint A
- A clinic operator can publish a dated schedule without Django admin.
- Existing bookings remain intact when rules change; stale or closed times cannot be newly booked.
- A later fee change cannot alter an existing booking or its payment order.

### Milestone B: patient self-service
Tasks 7-12: interrupted-request lookup, patient booking management, atomic reschedule, API, payment/notification effects, and patient reschedule UI.

### Checkpoint B
- A lost confirmation response can be recovered without duplicate booking.
- Patient cancellation and rescheduling use server-confirmed state and show refund consequences.
- Race tests prove a reschedule cannot lose the old booking or consume a second slot.

### Milestone C: clinic desk and launch gate
Tasks 13-18: staff-booked patient identity, manual/walk-in booking, visit-state actions, clinic desk UI, and full verification.

### Checkpoint C
- Staff cannot access another clinic's patients or appointments.
- Manual and online bookings share the same slot conflict rules.
- PostgreSQL concurrency tests, backend suite, schema checks, frontend typecheck/build, and staged browser journeys pass.

## Risks and mitigation

| Risk | Mitigation |
| --- | --- |
| Double booking or lost booking during reschedule | Deterministic lock order, database constraints, idempotency, and real PostgreSQL concurrency tests |
| Fee edits changing existing orders | Persist booking-time fee/currency before enabling more booking surfaces |
| Multi-clinic staff seeing the wrong patient | Explicit clinic assignment and denial tests for every read/write endpoint |
| Schedule edits invalidating existing appointments | Reconcile only unbooked future slots; show affected bookings and require a separate authorized change action |
| Interrupted browser or payment callback | User-scoped request lookup, durable server state, webhook reconciliation, and no optimistic confirmation |
| Scope exceeds a near-term deployment window | Ship only after each checkpoint; do not present the existing happy path as the full booking milestone |

## Product decisions to confirm before the dependent task

- Proposed reschedule rule: same doctor, clinic, and fee; other changes use cancel/refund/rebook.
- Cancellation timing: user chose patient self-service only before the appointment start time, with full refunds for eligible paid cancellations. Clinic/support actions remain separately authorized.
- Family and community-agent booking: decide the consent/identity model and whether these must be in the first clinic pilot. They are excluded from Milestones A-C under the current assumption.

## Verification commands and evidence

From backend: python -m pytest --create-db -q, python manage.py makemigrations --check --dry-run, and python manage.py check. From frontend: npm run typecheck, npm run test:auth, and npm run build. Run focused tests at each slice, then a staged browser exercise with two patients competing for one slot, a clinic operator, an interrupted booking request, cancellation, reschedule, notification delivery, and Razorpay test mode where configured. Record results and remaining limits in docs/.

Progress: Tasks 1-4 implemented. Appointment tests: 41 passed after schedule commands; payment tests: 8 passed; full backend suite: 338 passed before Task 4. Django system and migration checks passed. Slot publication, clinic UI, patient management, and clinic desk work remain.

