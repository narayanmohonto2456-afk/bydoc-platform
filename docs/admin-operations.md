# Admin operations

The `/dashboard/admin` workspace is available to an active superuser or a user with an active `StaffGrant`. Granting `is_staff` alone does not open operational queues or support cases. A superuser finds an account by username or email, then assigns and revokes the `provider`, `support`, `finance`, `schedule`, and `delivery` roles from the Staff access tab. Every grant change requires a reason and creates an `OperationsEvent`. Staff grants do not automatically grant Django admin access.

Run `python manage.py migrate` before opening the workspace. Existing superusers retain all operations roles. Existing non-superuser staff accounts need an explicit grant; the migration does not infer access from `is_staff`.

| Role | Queue and allowed actions |
|---|---|
| Provider | Review doctor and clinic applications with identity, registration, and duplicate checks; approve or reject with a reason; suspend or reactivate providers. Reactivation repeats the three checks and requires a verified doctor registration or an active clinic organization. |
| Support | View active cases, assign a support agent, reply, change case status, and escalate priority. Case events preserve comments and status history. The queue displays response targets of 4, 24, or 48 hours for high, normal, or low priority, measured from case creation. |
| Finance | Review payment and refund exceptions, verified webhook processing failures, and investigate or reconcile an intent. Reconciliation reads Razorpay and calls the existing payment services. Staff cannot manually set a payment or refund status. An investigation is human review state and does not change gateway state. |
| Schedule | Find a booking by reference or view upcoming and recently cancelled bookings, including open support counts. Cancel a confirmed appointment with a reason. Cancellation uses the existing slot, notification, and full-refund flow. A booking or payment record is never deleted. |
| Delivery | View failed or stale email, SMS, and other outbox messages, then retry a failed message with a reason. The retry uses the existing outbox claim and delivery worker. |

The operations API is under `/api/v1/operations/`. It applies role checks on every queue and action. Records returned to the delivery queue omit recipient details and message payloads. Operations events record actor, action, subject ID, reason, and minimal structured metadata. Only a superuser can read the operations audit endpoint. Support also retains its separate immutable case event history.

Before using finance actions in production, configure and verify Razorpay credentials, linked clinic accounts, and webhook delivery. The finance queue displays whether the gateway is configured. A signed webhook that fails processing appears in the webhook failure list without storing its payload or signature. Failed events require investigation and provider retry or reconciliation. Invalid signatures are rejected without creating a failure record.

The appointment desk currently offers cancellation only. Rescheduling, manual payment adjustments, and notification payload editing are intentionally absent until dedicated workflows and safeguards exist. The queue is bounded to 100 records; use the Django admin or database reporting for older history.
