"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { postJson } from "@/lib/api";

export default function RegisterPage() {
  const [username, setUsername] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    if (password !== confirm) { setError("Passwords do not match."); return; }
    setBusy(true);
    try {
      await postJson("/auth/register/", { username, password, first_name: firstName, last_name: lastName });
      setDone(true);
      setPassword("");
      setConfirm("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not create the account.");
    } finally {
      setBusy(false);
    }
  }

  return <div className="form-shell"><div className="panel">
    <span className="eyebrow">Get started</span><h1>Create your account</h1>
    <p>Registration does not sign you in. After creating your account, use your username and password to sign in.</p>
    {done ? <div className="message message-success" role="status">Your account is ready. <Link href="/login">Sign in now</Link>.</div> : <>
      {error && <div className="message message-error" role="alert">{error}</div>}
      <form onSubmit={submit}>
        <div className="field"><label htmlFor="username">Username</label><input id="username" autoComplete="username" maxLength={150} required value={username} onChange={event => setUsername(event.target.value)} /></div>
        <div className="field"><label htmlFor="first-name">First name (optional)</label><input id="first-name" autoComplete="given-name" maxLength={150} value={firstName} onChange={event => setFirstName(event.target.value)} /></div>
        <div className="field"><label htmlFor="last-name">Last name (optional)</label><input id="last-name" autoComplete="family-name" maxLength={150} value={lastName} onChange={event => setLastName(event.target.value)} /></div>
        <div className="field"><label htmlFor="password">Password</label><input id="password" type="password" autoComplete="new-password" maxLength={128} required value={password} onChange={event => setPassword(event.target.value)} /><span className="field-hint">Use a long, unique password. Common passwords are rejected.</span></div>
        <div className="field"><label htmlFor="confirm-password">Confirm password</label><input id="confirm-password" type="password" autoComplete="new-password" maxLength={128} required value={confirm} onChange={event => setConfirm(event.target.value)} /></div>
        <div className="form-actions"><button className="button" disabled={busy}>{busy ? "Creating…" : "Create account"}</button><Link href="/login">Already registered?</Link></div>
      </form>
    </>}
  </div></div>;
}
