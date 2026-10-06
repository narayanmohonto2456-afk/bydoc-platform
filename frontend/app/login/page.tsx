"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/components/AuthProvider";
import { PasswordField } from "@/components/PasswordField";

export default function LoginPage() {
  const router = useRouter();
  const { login } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      await login(username, password);
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
    <p>Use your SehatSaathi username and password.</p>
    {error && <div className="message message-error" role="alert">{error}</div>}
    <form onSubmit={submit}>
      <div className="field"><label htmlFor="username">Username</label><input id="username" autoComplete="username" required value={username} onChange={event => setUsername(event.target.value)} /></div>
      <PasswordField id="password" label="Password" autoComplete="current-password" value={password} onChange={setPassword} />
      <div className="form-actions"><button className="button" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button><Link href="/forgot-password">Forgot password?</Link></div>
    </form>
    <div className="divider" /><p>New to SehatSaathi? <Link href="/register">Create an account</Link>.</p>
  </div></div>;
}
