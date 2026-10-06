"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/components/AuthProvider";
import { PasswordField } from "@/components/PasswordField";
import { GoogleButton } from "@/components/GoogleButton";

export default function LoginPage() {
  const router = useRouter();
  const { login, googleLogin } = useAuth();
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      await login(identifier, password);
      router.replace("/account");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not sign in.");
    } finally {
      setBusy(false);
    }
  }

  return <div className="form-shell"><div className="panel">
    <span className="eyebrow">Welcome back</span>
    <h1>Sign in</h1>
    <p>Use your verified email address or username and password, or continue with Google.</p>
    {error && <div className="message message-error" role="alert">{error}</div>}
    <form onSubmit={submit}>
      <div className="field"><label htmlFor="identifier">Email or username</label><input id="identifier" autoComplete="username" required value={identifier} onChange={event => setIdentifier(event.target.value)} /></div>
      <PasswordField id="password" label="Password" autoComplete="current-password" value={password} onChange={setPassword} />
      <div className="form-actions"><button className="button" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button><Link href="/forgot-password">Forgot password?</Link></div>
    </form>
    <div className="auth-divider"><span>or</span></div>
    <GoogleButton onCredential={async credential => { await googleLogin(credential); router.replace("/account"); }} />
    <div className="divider" /><p>New to SehatSaathi? <Link href="/register">Create an account</Link>.</p>
  </div></div>;
}
