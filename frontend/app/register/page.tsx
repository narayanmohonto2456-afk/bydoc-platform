"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { postJson } from "@/lib/api";
import { PasswordField, PasswordStrength } from "@/components/PasswordField";
import { GoogleButton } from "@/components/GoogleButton";
import { AuthShowcase } from "@/components/AuthShowcase";
import { useRouter } from "next/navigation";
import { useAuth } from "@/components/AuthProvider";

export default function RegisterPage() {
  const router = useRouter();
  const { googleLogin } = useAuth();
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
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
      await postJson("/auth/register/", { username, email, password, first_name: firstName, last_name: lastName });
      setDone(true);
      setPassword("");
      setConfirm("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not create the account.");
    } finally {
      setBusy(false);
    }
  }

  return <div className="auth-page"><div className="auth-layout">
    <AuthShowcase mode="register" />
    <section className="auth-form-panel" aria-labelledby="register-heading">
    <span className="eyebrow">Your care starts here</span><h1 id="register-heading">Create your account<span className="auth-heading-dot">.</span></h1>
    <p className="auth-intro">A few details now make every future visit easier.</p>
    {done ? <div className="message message-success" role="status">Your account is ready. Check your email for a verification link. You can <Link href="/login">sign in with your username</Link> now and use your email after verification.</div> : <>
      {error && <div className="message message-error" role="alert">{error}</div>}
      <form onSubmit={submit}>
        <div className="auth-field-pair">
          <div className="field"><label htmlFor="first-name">First name <span className="auth-optional">optional</span></label><input id="first-name" autoComplete="given-name" maxLength={150} placeholder="Your first name" value={firstName} onChange={event => setFirstName(event.target.value)} /></div>
          <div className="field"><label htmlFor="last-name">Last name <span className="auth-optional">optional</span></label><input id="last-name" autoComplete="family-name" maxLength={150} placeholder="Your last name" value={lastName} onChange={event => setLastName(event.target.value)} /></div>
        </div>
        <div className="field"><label htmlFor="username">Username</label><input id="username" autoComplete="username" maxLength={150} placeholder="Choose a username" required value={username} onChange={event => setUsername(event.target.value)} /></div>
        <div className="field"><label htmlFor="email">Email address</label><input id="email" type="email" autoComplete="email" placeholder="you@example.com" required value={email} onChange={event => setEmail(event.target.value)} /></div>
        <PasswordField id="password" label="Password" autoComplete="new-password" value={password} onChange={setPassword} hint="Use a long, unique password. Common passwords are rejected." />
        <PasswordStrength password={password} />
        <PasswordField id="confirm-password" label="Confirm password" autoComplete="new-password" value={confirm} onChange={setConfirm} />
        {confirm && <span className={`match-hint${confirm === password ? " match-good" : " match-pending"}`} role="status">{confirm === password ? "Passwords match." : "Passwords do not match yet."}</span>}
        <div className="auth-form-actions"><button className="button button-large" disabled={busy}>{busy ? "Creating…" : "Create account"}<span aria-hidden="true">→</span></button></div>
      </form>
      <div className="auth-divider"><span>or continue with</span></div>
      <GoogleButton onCredential={async credential => { await googleLogin(credential); router.replace("/account"); }} />
    </>}
    <p className="auth-switch">Already have an account? <Link href="/login">Sign in <span aria-hidden="true">↗</span></Link></p>
    </section>
  </div></div>;
}
