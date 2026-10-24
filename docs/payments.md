# Consultation payments with Razorpay Route

BYdoc confirms a booking first. The patient can then pay the declared consultation fee online or at the clinic. Online checkout is available only for a clinic with an enabled, approved Razorpay Route linked account and a positive INR consultation fee. The platform does not store card data. The API creates an order that routes the full fee to that clinic's linked account; the appointment snapshots the fee and currency at booking, and the order snapshots that amount in paise. Later fee edits cannot change either amount. Historical appointments without a trustworthy booking-time fee cannot start a new online charge; an existing pending order may still be resumed while its original linked clinic account remains enabled.

The browser receives only the Razorpay key ID and order ID. The key secret and webhook secret remain on the API. A checkout callback is accepted only after HMAC verification and a server-side payment lookup confirms `captured`, the matching order, amount, and currency. Signed webhooks and a periodic reconciliation task cover interrupted browser sessions. Duplicate order calls, captures, webhooks, and refund jobs are handled idempotently. Payment status is separate from appointment status.

When a paid confirmed appointment is cancelled, the same database transaction marks its payment `refund_due`. Celery Beat's `payments.reconcile` task requests a **full refund** with `reverse_all=1`, so Razorpay also reverses the Route transfer. A capture that arrives after cancellation enters `refund_due` directly. The worker checks existing refunds before retrying a request, then polls until the provider reports `processed`. A failed refund moves to `review`; an operator must resolve it in Razorpay and have an authorized backend operator reconcile the payment record. Refund timing to the patient's original payment method is controlled by Razorpay and the issuing bank.

## Enable in test mode

1. Obtain a Razorpay platform account with Route access. Onboard each clinic as a linked account in Razorpay; verify its settlement details. Do not put a clinic's Razorpay API secret in BYdoc.
2. Add `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, and a separately generated `RAZORPAY_WEBHOOK_SECRET` to the backend environment. Set `RAZORPAY_PAYMENTS_ENABLED=true`. Keep these out of Git and the frontend environment.
3. In Django admin, create a **Clinic payment account** for each participating clinic, enter its `acc_...` linked account ID, and enable it. This administration form is superuser-only. Configure the doctor's affiliation fee in INR.
4. In Razorpay, configure a webhook to `https://<API_HOST>/api/v1/payments/webhook/razorpay/` using the same webhook secret. Subscribe to `payment.captured`, `refund.processed`, and `refund.failed`. Allow HTTPS requests to reach the API. Start the Celery worker and Beat so reconciliation and refunds run.
5. With **test keys**, book a slot, pay using Razorpay test checkout, verify that the payment is `captured`, cancel the appointment, and verify `refund_due` → `refund_pending` → `refunded` and the transfer reversal in Razorpay. Check duplicate callbacks and an interrupted checkout. Test a refund after a transfer has settled as part of launch review.

Production settings reject test key IDs while payments are enabled. Enable live payments only after live Route access, linked clinic verification, webhook delivery, provider capture settings, monitoring, and refund reconciliation are tested. If online payments are disabled, patients can still book and pay at the clinic. The platform does not automatically charge or refund pay-at-clinic bookings.

## Operational checks

- Inspect `PaymentIntent` in Django admin for `refund_due` older than a few minutes, `refund_pending` older than the expected provider processing period, `review`, or a nonempty `last_error`.
- Compare captured payments, Route transfers, and processed refunds against Razorpay's dashboard or reports each day. Resolve discrepancies before settlement close.
- Treat a booking as paid only when the payment status is `captured`. An `authorized` payment, browser success message, or booking confirmation alone does not prove capture.

Razorpay references: [Route transfer via order](https://razorpay.com/route/), [Route refund and reverse transfer](https://d6xcmfyh68wv8.cloudfront.net/docs/api/payments/route/), and [Python checkout integration](https://razorpay.com/docs/server-integration/python/test-app/).
