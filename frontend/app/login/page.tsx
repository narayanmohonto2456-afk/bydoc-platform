"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/components/AuthProvider";
import { PasswordField } from "@/components/PasswordField";
import { GoogleButton } from "@/components/GoogleButton";
import { apiRequest, postJson } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const { login, googleLogin, otpLogin } = useAuth();
  const [method, setMethod] = useState<"password" | "email" | "sms">("password");
  const [codeRequested, setCodeRequested] = useState(false);
  const [code, setCode] = useState("");
  const [smsAvailable, setSmsAvailable] = useState(false);
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    apiRequest<{ email: boolean; sms: boolean }>("/auth/otp/status/")
      .then(result => setSmsAvailable(result.sms))
      .catch(() => setSmsAvailable(false));
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      if (method === "password") {
        await login(identifier, password);
        router.replace("/dashboard");
      } else if (!codeRequested) {
        await postJson("/auth/otp/request/", { channel: method, identifier });
        setCodeRequested(true);
      } else {
        await otpLogin(method, identifier, code);
        router.replace("/dashboard");
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not sign in.");
    } finally {
      setBusy(false);
    }
  }

  return <div className="form-shell"><div className="panel">
    <span className="eyebrow">Welcome back</span>
    <h1>Sign in</h1>
    <p>Sign in with a password, a one-time code sent to a verified contact, or Google.</p>
    <div className="auth-methods" role="group" aria-label="Sign-in method">
      <button type="button" aria-pressed={method === "password"} onClick={() => { setMethod("password"); setCodeRequested(false); setError(""); }}>Password</button>
      <button type="button" aria-pressed={method === "email"} onClick={() => { setMethod("email"); setCodeRequested(false); setError(""); }}>Email code</button>
      <button type="button" aria-pressed={method === "sms"} disabled={!smsAvailable} onClick={() => { setMethod("sms"); setCodeRequested(false); setError(""); }}>SMS code</button>
    </div>
    {!smsAvailable && <p className="field-hint">SMS sign-in will be available after the BYdoc sender is configured. Email codes are available for verified addresses.</p>}
    {error && <div className="message message-error" role="alert">{error}</div>}
    <form onSubmit={submit}>
      <div className="field"><label htmlFor="identifier">{method === "password" ? "Email or username" : method === "email" ? "Verified email" : "Verified phone (+country code)"}</label><input id="identifier" type={method === "email" ? "email" : method === "sms" ? "tel" : "text"} autoComplete={method === "sms" ? "tel" : "username"} required value={identifier} onChange={event => { setIdentifier(event.target.value); setCodeRequested(false); }} disabled={busy} /></div>
      {method === "password" ? <PasswordField id="password" label="Password" autoComplete="current-password" value={password} onChange={setPassword} /> : codeRequested && <div className="field"><label htmlFor="otp-code">Six-digit code</label><input id="otp-code" inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}" maxLength={6} required value={code} onChange={event => setCode(event.target.value.replace(/\D/g, ""))} /><span className="field-hint">Codes expire after 10 minutes. Never share yours.</span></div>}
      {codeRequested && method !== "password" && <p role="status">If this {method === "email" ? "email" : "phone"} is eligible, a code is on its way. Delivery may take a moment.</p>}
      <div className="form-actions"><button className="button" disabled={busy}>{busy ? "Please wait…" : method === "password" ? "Sign in" : codeRequested ? "Verify and sign in" : "Send code"}</button>{method === "password" ? <Link href="/forgot-password">Forgot password?</Link> : codeRequested && <button type="button" className="button button-secondary" onClick={() => { setCodeRequested(false); setCode(""); }}>Request a new code</button>}</div>
    </form>
    <div className="auth-divider"><span>or</span></div>
    <GoogleButton onCredential={async credential => { await googleLogin(credential); router.replace("/dashboard"); }} />
    <div className="divider" /><p>New to BYdoc? <Link href="/register">Create an account</Link>.</p>
  </div></div>;
}
