"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { postJson } from "@/lib/api";

export default function VerifyEmailPage() {
  const [token, setToken] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const value = new URLSearchParams(window.location.hash.slice(1)).get("token");
    setToken(value);
    if (value) window.history.replaceState(null, "", window.location.pathname);
  }, []);

  async function confirm() {
    if (!token) return;
    setError("");
    setBusy(true);
    try {
      await postJson<void>("/auth/email/verify/confirm/", { token });
      setToken(null);
      setDone(true);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not verify this email.");
    } finally {
      setBusy(false);
    }
  }

  return <div className="form-shell"><div className="panel">
    <span className="eyebrow">Account security</span><h1>Verify your email</h1>
    {done ? <div className="message message-success" role="status">Your email is verified. <Link href="/account">Return to your account</Link>.</div> : <>
      <p>Confirm the email address you requested. Links expire after 30 minutes and can be used once.</p>
      {error && <div className="message message-error" role="alert">{error}</div>}
      {token ? <button className="button" onClick={confirm} disabled={busy}>{busy ? "Verifying…" : "Verify email"}</button> : <div className="message message-error" role="alert">No verification link was found. Request a new link from your account.</div>}
    </>}
  </div></div>;
}
