"use client";

import { useCallback, useEffect, useState } from "react";
import { apiRequest, postJson } from "@/lib/api";

type PaymentStatus = {
  available: boolean;
  status: "pay_at_clinic" | "pending" | "captured" | "refund_due" | "refund_pending" | "refunded" | "review";
  amount_paise: number | null;
  currency: string;
  refund_id: string | null;
};
type Order = { key_id: string; order_id: string; amount_paise: number; currency: string };
type CheckoutResult = { razorpay_order_id: string; razorpay_payment_id: string; razorpay_signature: string };
type CheckoutOptions = {
  key: string; amount: number; currency: string; order_id: string; name: string;
  description: string; handler: (result: CheckoutResult) => void;
  modal: { ondismiss: () => void };
};
type CheckoutWindow = Window & { Razorpay?: new (options: CheckoutOptions) => { open: () => void } };

let checkoutScript: Promise<void> | null = null;
function loadCheckout(): Promise<void> {
  if ((window as CheckoutWindow).Razorpay) return Promise.resolve();
  if (!checkoutScript) {
    checkoutScript = new Promise<void>((resolve, reject) => {
      const script = document.createElement("script");
      script.src = "https://checkout.razorpay.com/v1/checkout.js";
      script.async = true;
      script.onload = () => resolve();
      script.onerror = () => reject(new Error("Could not load Razorpay checkout."));
      document.body.appendChild(script);
    }).catch(error => { checkoutScript = null; throw error; });
  }
  return checkoutScript!;
}

export function AppointmentPayment({ appointmentId }: { appointmentId: string }) {
  const [payment, setPayment] = useState<PaymentStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const refresh = useCallback(async () => {
    const result = await apiRequest<PaymentStatus>(`/payments/appointments/${appointmentId}/`);
    setPayment(result);
  }, [appointmentId]);

  useEffect(() => {
    let active = true;
    apiRequest<PaymentStatus>(`/payments/appointments/${appointmentId}/`)
      .then(result => { if (active) setPayment(result); })
      .catch(() => { if (active) setError("Could not load payment status. Refresh this page to try again."); });
    return () => { active = false; };
  }, [appointmentId]);

  async function payNow() {
    setBusy(true);
    setError("");
    try {
      const order = await postJson<Order>(`/payments/appointments/${appointmentId}/order/`, {});
      await loadCheckout();
      const Checkout = (window as CheckoutWindow).Razorpay;
      if (!Checkout) throw new Error("Could not open Razorpay checkout.");
      new Checkout({
        key: order.key_id,
        amount: order.amount_paise,
        currency: order.currency,
        order_id: order.order_id,
        name: "BYdoc",
        description: "Clinic consultation fee",
        handler: async result => {
          try {
            const verified = await postJson<PaymentStatus>(`/payments/appointments/${appointmentId}/verify/`, result);
            setPayment(verified);
            if (verified.status !== "captured") setError("Payment is being checked. Refresh this page for its latest status.");
          } catch {
            setError("Payment could not be confirmed yet. Please check its status before trying again.");
            await refresh().catch(() => undefined);
          } finally {
            setBusy(false);
          }
        },
        modal: { ondismiss: () => { setBusy(false); refresh().catch(() => undefined); } },
      }).open();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not start payment.");
      setBusy(false);
    }
  }

  if (!payment && !error) return <p role="status">Checking payment options…</p>;
  return <div className="appointment-payment">
    {payment?.status === "captured" && <p role="status">Consultation fee paid online.</p>}
    {payment?.status === "refund_due" && <p role="status">Full refund is being prepared.</p>}
    {payment?.status === "refund_pending" && <p role="status">Full refund requested. The provider is processing it.</p>}
    {payment?.status === "refunded" && <p role="status">Full refund processed.</p>}
    {payment?.status === "review" && <p role="alert">Payment needs support review. Please do not pay again.</p>}
    {payment?.available && ["pay_at_clinic", "pending"].includes(payment.status) && <>
      <p>Choose Pay now or pay the consultation fee at the clinic.</p>
      <button type="button" className="button button-secondary" disabled={busy} onClick={payNow}>{busy ? "Opening secure checkout…" : "Pay now with Razorpay"}</button>
    </>}
    {payment && !payment.available && payment.status === "pay_at_clinic" && <p>Pay the consultation fee at the clinic.</p>}
    {error && <p className="message message-error" role="alert">{error}</p>}
    {payment?.status === "pending" && <button type="button" className="button button-secondary" onClick={() => refresh().catch(() => setError("Could not refresh payment status."))}>Refresh payment status</button>}
  </div>;
}
