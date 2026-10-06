"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { postJson } from "@/lib/api";

export default function ForgotPasswordPage() {
  const [address, setAddress] = useState("");
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      await postJson("/auth/password/reset/request/", { address });
      setDone(true);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not submit the request.");
    } finally {
      setBusy(false);
    }
  }

  return <div className="form-shell"><div className="panel">
    <span className="eyebrow">Account help</span><h1>Reset your password</h1>
    <p>Enter your verified email address. If it is eligible, we will send a reset link.</p>
    {done ? <div className="message message-success" role="status">If the address is eligible, an email will be sent. Check your inbox and spam folder.</div> : <>
      {error && <div className="message message-error" role="alert">{error}</div>}
      <form onSubmit={submit}>
        <div className="field"><label htmlFor="address">Email address</label><input id="address" type="email" autoComplete="email" required value={address} onChange={event => setAddress(event.target.value)} /></div>
        <div className="form-actions"><button className="button" disabled={busy}>{busy ? "Submitting…" : "Send reset link"}</button><Link href="/login">Back to sign in</Link></div>
      </form>
    </>}
  </div></div>;
}
