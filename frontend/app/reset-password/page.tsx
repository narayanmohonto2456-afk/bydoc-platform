"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { postJson } from "@/lib/api";

export default function ResetPasswordPage() {
  const [token, setToken] = useState<string | null>(null);
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const value = new URLSearchParams(window.location.hash.slice(1)).get("token");
    setToken(value);
    if (value) window.history.replaceState(null, "", window.location.pathname);
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token) return;
    setError("");
    if (password !== confirm) { setError("Passwords do not match."); return; }
    setBusy(true);
    try {
      await postJson<void>("/auth/password/reset/confirm/", { token, password });
      setPassword("");
      setConfirm("");
      setToken(null);
      setDone(true);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not reset your password.");
    } finally {
      setBusy(false);
    }
  }

  return <div className="form-shell"><div className="panel">
    <span className="eyebrow">Account help</span><h1>Choose a new password</h1>
    {done ? <div className="message message-success" role="status">Your password has been changed. Existing sessions were signed out. <Link href="/login">Sign in again</Link>.</div> : <>
      <p>This link works once and expires 30 minutes after it was requested.</p>
      {error && <div className="message message-error" role="alert">{error}</div>}
      {token ? <form onSubmit={submit}>
        <div className="field"><label htmlFor="password">New password</label><input id="password" type="password" autoComplete="new-password" maxLength={128} required value={password} onChange={event => setPassword(event.target.value)} /></div>
        <div className="field"><label htmlFor="confirm">Confirm new password</label><input id="confirm" type="password" autoComplete="new-password" maxLength={128} required value={confirm} onChange={event => setConfirm(event.target.value)} /></div>
        <button className="button" disabled={busy}>{busy ? "Changing…" : "Change password"}</button>
      </form> : <div className="message message-error" role="alert">No reset link was found. <Link href="/forgot-password">Request another link</Link>.</div>}
    </>}
  </div></div>;
}
