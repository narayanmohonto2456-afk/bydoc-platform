# BYdoc appointment booking task list

All boxes are open. Complete a task only after its acceptance criteria and verification pass. The design and open decisions are in [plan.md](plan.md). Run focused checks during each slice; run the full suite at checkpoints.

## Milestone A: trustworthy inventory and price

### Task 1: Snapshot the booking fee
**Description:** Persist the declared fee and currency on each new appointment at confirmation. Historical appointments with no reliable snapshot remain explicitly unknown.
**Acceptance criteria:**
- [x] A new appointment retains its fee and currency after the affiliation fee changes.
- [x] Existing records migrate without invented historical prices.
**Verification:** Focused appointment tests; migration check.
**Dependencies:** None.
**Files likely touched:** backend/apps/appointments/models.py, a new appointments migration, backend/apps/appointments/services.py, backend/apps/appointments/serializers.py, backend/apps/appointments/test_api.py.
**Estimated scope:** Medium.

### Task 2: Make payments use the booking snapshot
**Description:** Create optional Razorpay orders from the committed appointment price and keep the existing full-refund path.
**Acceptance criteria:**
- [x] A later fee edit cannot alter a new or pending order for that appointment.
- [x] An old appointment without a trusted fee snapshot cannot silently charge the current price.
**Verification:** Payment capture/refund tests, including a fee edit after booking.
**Dependencies:** 1.
**Files likely touched:** backend/apps/payments/services.py, backend/apps/payments/test_payments.py, docs/payments.md.
**Estimated scope:** Small.

### Checkpoint: after Tasks 1-2
- [x] Focused appointment and payment tests pass.
- [x] Booking and payment display the same immutable amount.

### Task 3: Scope clinic staff to assigned clinics
**Description:** Add explicit clinic assignments for receptionists while owners and managers retain organization-wide access. Centralize the authorization check for schedule and booking operations.
**Acceptance criteria:**
- [x] A receptionist assigned to Clinic A cannot read or change Clinic B data in the same organization.
- [x] Suspended or revoked membership/assignment immediately loses access.
**Verification:** Organization and dashboard permission tests for allowed and denied clinics.
**Dependencies:** None.
**Files likely touched:** backend/apps/organizations/models.py, a new organizations migration, backend/apps/organizations/permissions.py, backend/apps/organizations/tests.py, backend/apps/dashboard/views.py.
**Estimated scope:** Medium.

### Task 4: Add clinic schedule commands
**Description:** Expose validated weekly rules, leave/closure exceptions, and slot blocking through clinic-scoped API commands, with actor and reason recorded.
**Acceptance criteria:**
- [x] Authorized staff can publish rules and exceptions; invalid or overlapping input is rejected.
- [x] Every change has an actor, timestamp, and reason; a different clinic receives 404/403.
**Verification:** New schedule API tests covering timezone boundaries, permissions, and conflicts.
**Dependencies:** 3.
**Files likely touched:** backend/apps/appointments/serializers.py, backend/apps/appointments/views.py, backend/apps/appointments/urls.py, backend/apps/appointments/services.py, backend/apps/appointments/test_schedule_api.py.
**Estimated scope:** Medium.

### Task 5: Reconcile published slots safely
**Description:** Generate/reconcile a bounded future slot horizon after schedule edits and periodically; report bookings affected by leave or closure.
**Acceptance criteria:**
- [ ] Repeated publication creates no duplicate slots and never deletes booked or actively held slots.
- [ ] New booking is blocked during closed time; existing affected bookings are surfaced for staff action.
**Verification:** PostgreSQL tests for repeat runs, overlapping rules, closure, and existing bookings; worker task check.
**Dependencies:** 4.
**Files likely touched:** backend/apps/appointments/services.py, backend/apps/appointments/tasks.py, backend/apps/appointments/test_schedule_api.py, backend/config/celery.py, backend/apps/clinics/models.py.
**Estimated scope:** Medium.

### Task 6: Build the clinic schedule editor
**Description:** Let authorized clinic staff edit rules and exceptions, review generated slots and affected bookings, and see schedule freshness.
**Acceptance criteria:**
- [ ] Staff can complete a schedule update without Django admin.
- [ ] Save conflicts and the effect on existing appointments are visible before staff leave the page.
**Verification:** Frontend typecheck/build and browser check at desktop and narrow viewport.
**Dependencies:** 3-5.
**Files likely touched:** frontend/app/dashboard/clinic/schedule/page.tsx, frontend/components/ClinicSchedule.tsx, frontend/app/globals.css.
**Estimated scope:** Medium.

### Checkpoint A: after Tasks 3-6
- [ ] Clinic scheduling works end to end with assigned staff.
- [ ] Active appointments are preserved and closed time is unavailable.
- [ ] Backend focused tests, frontend typecheck and build pass.

## Milestone B: patient self-service

### Task 7: Recover interrupted confirmations
**Description:** Add a user-scoped lookup by booking request ID. Retain the request ID in the browser until the server result is known.
**Acceptance criteria:**
- [ ] A lost response after commit resolves to the existing booking without another appointment.
- [ ] An unrelated user cannot discover the request or its booking.
**Verification:** API timeout/retry and ownership tests; browser interruption exercise.
**Dependencies:** None.
**Files likely touched:** backend/apps/appointments/views.py, backend/apps/appointments/urls.py, backend/apps/appointments/test_api.py, frontend/app/appointments/page.tsx.
**Estimated scope:** Medium.

### Task 8: Add patient appointment detail and cancellation
**Description:** Show authoritative upcoming, past, and cancelled records, with a consequence review before using the existing cancellation API.
**Acceptance criteria:**
- [ ] A patient can cancel an eligible confirmed booking and sees the returned status and refund state.
- [ ] Other patients cannot see or cancel it; failed requests never display success.
**Verification:** Existing cancellation API tests plus frontend typecheck/build and browser journey.
**Dependencies:** 2, 7.
**Files likely touched:** frontend/app/dashboard/patient/page.tsx, frontend/app/appointments/[appointmentId]/page.tsx, frontend/components/RoleDashboard.tsx, frontend/app/globals.css.
**Estimated scope:** Medium.

### Task 9: Implement an atomic reschedule service
**Description:** Add an append-only change event and move a confirmed appointment to a held slot with deterministic locking and idempotency.
**Acceptance criteria:**
- [ ] A competing booking or reschedule cannot double-book or strand both the old and new slots.
- [ ] The appointment identity and full change history survive a successful move; an error leaves the old booking intact.
**Verification:** Real PostgreSQL concurrency and retry tests, including expired holds.
**Dependencies:** 1, 3.
**Files likely touched:** backend/apps/appointments/models.py, a new appointments migration, backend/apps/appointments/services.py, backend/apps/appointments/test_reschedule.py.
**Estimated scope:** Medium.

### Checkpoint: after Tasks 7-9
- [ ] Recovery, cancellation, and core reschedule race tests pass.
- [ ] No second confirmed appointment can consume one slot.

### Task 10: Expose patient and clinic reschedule API
**Description:** Add a scoped command and stable conflict responses for same-doctor, same-clinic, same-fee rescheduling.
**Acceptance criteria:**
- [ ] Patient or authorized clinic staff can move an eligible booking; others get a non-disclosing denial.
- [ ] Repeating the same request returns its original outcome.
**Verification:** API tests for ownership, clinic scope, idempotency, and 409 conflicts.
**Dependencies:** 9.
**Files likely touched:** backend/apps/appointments/views.py, backend/apps/appointments/serializers.py, backend/apps/appointments/urls.py, backend/apps/appointments/test_reschedule.py.
**Estimated scope:** Medium.

### Task 11: Reconcile payment and notifications after reschedule
**Description:** Preserve a valid paid intent only under the approved same-fee rule; replace old reminders and send one change notice after commit.
**Acceptance criteria:**
- [ ] A paid booking is never silently moved to a different fee or merchant account.
- [ ] Old reminders are cancelled and duplicate retries create no duplicate change notices.
**Verification:** Payment and notification integration tests, including late webhook events.
**Dependencies:** 9-10.
**Files likely touched:** backend/apps/payments/services.py, backend/apps/payments/test_payments.py, backend/apps/notifications/services.py, backend/apps/notifications/test_integration.py, backend/apps/appointments/services.py.
**Estimated scope:** Medium.

### Task 12: Add patient reschedule UI
**Description:** Reuse slot search and hold behavior, show the old and replacement visit, payment implications, and only confirm after the API succeeds.
**Acceptance criteria:**
- [ ] An expired/rejected replacement hold leaves the original appointment clearly intact.
- [ ] A successful move shows the new time, history, and updated payment state.
**Verification:** Frontend typecheck/build and browser race/error review.
**Dependencies:** 10-11.
**Files likely touched:** frontend/app/appointments/[appointmentId]/page.tsx, frontend/components/AppointmentReschedule.tsx, frontend/app/globals.css.
**Estimated scope:** Medium.

### Checkpoint B: after Tasks 10-12
- [ ] Patient book, recover, cancel, and reschedule journeys pass in a browser.
- [ ] Payment/refund and reminder state match the authoritative appointment.

## Milestone C: clinic desk and launch gate

### Task 13: Define staff-booked patient identity and source
**Description:** Record whether a booking came from patient, receptionist, or walk-in; add a minimal walk-in identity with consent and restricted visibility without creating a fake account.
**Acceptance criteria:**
- [ ] Staff can distinguish online, assisted, and walk-in records without exposing one patient's data to another.
- [ ] Identity and consent fields are minimized and auditable.
**Verification:** Migration and model/privacy tests.
**Dependencies:** 3.
**Files likely touched:** backend/apps/appointments/models.py, a new appointments migration, backend/apps/appointments/test_clinic_booking.py, backend/apps/appointments/serializers.py.
**Estimated scope:** Medium.

### Task 14: Add receptionist booking commands
**Description:** Let assigned staff book an existing patient or walk-in through the same slot lock and conflict rules as patient booking.
**Acceptance criteria:**
- [ ] Manual and walk-in bookings cannot bypass a held/booked slot or provider verification.
- [ ] Only assigned staff can act; repeated submission cannot create duplicates.
**Verification:** Clinic API tests and a two-actor final-slot PostgreSQL race test.
**Dependencies:** 3, 13.
**Files likely touched:** backend/apps/appointments/services.py, backend/apps/appointments/views.py, backend/apps/appointments/urls.py, backend/apps/appointments/test_clinic_booking.py.
**Estimated scope:** Medium.

### Task 15: Add clinic visit-state commands
**Description:** Expose authorized check-in, completion, and no-show transitions with actor/time/reason; reuse cancellation and rescheduling commands.
**Acceptance criteria:**
- [ ] Invalid transitions and wrong-clinic actions are rejected without changing appointment truth.
- [ ] A cancellation racing check-in has one valid outcome and an auditable event.
**Verification:** Transition, clinic-permission, and concurrency tests.
**Dependencies:** 3, 9, 13.
**Files likely touched:** backend/apps/appointments/services.py, backend/apps/appointments/views.py, backend/apps/appointments/urls.py, backend/apps/appointments/test_clinic_booking.py.
**Estimated scope:** Medium.

### Checkpoint: after Tasks 13-15
- [ ] Assigned staff can manage real bookings without cross-clinic access.
- [ ] Manual and patient bookings have equivalent conflict protection.

### Task 16: Build the clinic appointment desk
**Description:** Replace the read-only list with searchable daily records and clear manual booking, check-in, no-show, cancel, and reschedule actions.
**Acceptance criteria:**
- [ ] Receptionists can perform common tasks on desktop and phone without Django admin.
- [ ] The screen shows source, status, latest update, conflicts, and affected appointments.
**Verification:** Frontend typecheck/build and keyboard/browser usability review.
**Dependencies:** 6, 10-11, 14-15.
**Files likely touched:** frontend/components/RoleDashboard.tsx, frontend/components/ClinicAppointmentDesk.tsx, frontend/app/dashboard/clinic/page.tsx, frontend/app/globals.css.
**Estimated scope:** Medium.

### Task 17: Run booking integrity and security gate
**Description:** Consolidate real PostgreSQL race tests and verify migration, permissions, API schema, notification idempotency, and the frontend build.
**Acceptance criteria:**
- [ ] Final-slot booking, timeout retry, hold expiry, cancellation/check-in, and reschedule races pass repeatedly.
- [ ] Full backend suite, schema checks, frontend typecheck, auth test, and production build pass.
**Verification:** python -m pytest --create-db -q; python manage.py makemigrations --check --dry-run; python manage.py check; npm run typecheck; npm run test:auth; npm run build.
**Dependencies:** 1-16.
**Files likely touched:** Focused test files and docs/ only where failures or contract changes require updates.
**Estimated scope:** Medium.

### Task 18: Verify the staged browser journey
**Description:** Exercise representative patient and clinic accounts over HTTPS with actual worker/Beat jobs and optional Razorpay test mode.
**Acceptance criteria:**
- [ ] Book, recover, cancel, reschedule, manual booking, check-in, reminder, and refund states match server records.
- [ ] Findings, limits, and launch decision are recorded in docs/ with no unresolved critical booking-integrity defect.
**Verification:** Browser and network review plus staging logs, database checks, and a written verification record.
**Dependencies:** 17.
**Files likely touched:** docs/verification-appointment-booking.md.
**Estimated scope:** Medium.

### Checkpoint C: after Tasks 16-18
- [ ] Pilot clinic staff can operate schedules and today's appointments.
- [ ] Patient and clinic journeys pass with representative data.
- [ ] Human review of the verification record before release.
