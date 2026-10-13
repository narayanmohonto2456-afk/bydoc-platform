"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/components/AuthProvider";
import { apiRequest, postJson } from "@/lib/api";

type Kind = "doctor" | "clinic";
type ApplicationStatus = {
  id: string | null;
  status: "not_submitted" | "pending" | "approved" | "rejected";
  detail: string;
  submitted_at: string | null;
  reviewed_at: string | null;
};

const fields = {
  doctor: [
    { name: "display_name", label: "Name shown to patients", max: 200 },
    { name: "registered_name", label: "Name on medical registration", max: 200 },
    { name: "council_name", label: "Medical council or registration authority", max: 200 },
    { name: "registration_number", label: "Registration number", max: 100 },
  ],
  clinic: [
    { name: "clinic_name", label: "Clinic name", max: 200 },
    { name: "manager_name", label: "Responsible manager or owner", max: 200 },
    { name: "registration_authority", label: "Clinic registration or licence authority", max: 200 },
    { name: "registration_number", label: "Clinic registration or licence number", max: 100 },
    { name: "address_line_1", label: "Street address", max: 255 },
    { name: "locality", label: "Locality", max: 120 },
    { name: "district", label: "District", max: 120 },
    { name: "state", label: "State", max: 120 },
  ],
} as const;

function StatusCard({ application }: { application: ApplicationStatus }) {
  return <div className={`message ${application.status === "approved" ? "message-success" : ""}`} role="status">
    <strong>{application.status === "pending" ? "Application under review" : application.status === "approved" ? "Application approved" : "Application reviewed"}</strong>
    <p>{application.detail}</p>
    {application.submitted_at && <p>Submitted {new Intl.DateTimeFormat("en-IN", { dateStyle: "medium" }).format(new Date(application.submitted_at))}</p>}
    {application.status === "approved" && <Link href="/dashboard">Open your dashboard</Link>}
  </div>;
}

export default function JoinPage() {
  const { user, loading } = useAuth();
  const [kind, setKind] = useState<Kind>("doctor");
  const [applications, setApplications] = useState<Partial<Record<Kind, ApplicationStatus>>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!user) return;
    let active = true;
    Promise.all([
      apiRequest<ApplicationStatus>("/onboarding/doctor/"),
      apiRequest<ApplicationStatus>("/onboarding/clinic/"),
    ]).then(([doctor, clinic]) => {
      if (active) setApplications({ doctor, clinic });
    }).catch(() => { if (active) setError("Could not load your applications. Refresh to try again."); });
    return () => { active = false; };
  }, [user?.id]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    setBusy(true);
    setError("");
    const data = new FormData(form);
    const body: Record<string, unknown> = Object.fromEntries(data.entries());
    body.attestation = data.get("attestation") === "on";
    if (kind === "doctor") {
      body.registration_year = data.get("registration_year") ? Number(data.get("registration_year")) : null;
    }
    try {
      const application = await postJson<ApplicationStatus>(`/onboarding/${kind}/`, body);
      setApplications(current => ({ ...current, [kind]: application }));
      form.reset();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not submit your application.");
    } finally {
      setBusy(false);
    }
  }

  const application = applications[kind];
  return <div className="wide-shell join-shell">
    <header className="booking-heading"><span className="eyebrow">Join BYdoc</span><h1>Bring your practice to patients</h1><p>Submit your details for an independent review. Your listing appears only after approval.</p></header>
    <div className="join-tabs" role="group" aria-label="Application type">
      <button type="button" className={`button ${kind === "doctor" ? "" : "button-secondary"}`} aria-pressed={kind === "doctor"} onClick={() => { setKind("doctor"); setError(""); }}>I am a doctor</button>
      <button type="button" className={`button ${kind === "clinic" ? "" : "button-secondary"}`} aria-pressed={kind === "clinic"} onClick={() => { setKind("clinic"); setError(""); }}>I represent a clinic</button>
    </div>
    <section className="panel join-panel">
      <h2>{kind === "doctor" ? "Doctor application" : "Clinic application"}</h2>
      <p className="dashboard-note">Sign in with a verified email. BYdoc reviews the registration details and may contact you before approval. Please do not enter patient information.</p>
      {loading ? <p role="status">Checking your account…</p> : !user ? <p><Link href="/register">Create an account</Link> or <Link href="/login">sign in</Link> before applying.</p> : !application ? !error && <p role="status">Loading application status…</p> : application.status === "pending" || application.status === "approved" ? <StatusCard application={application} /> : <>
        {application.status === "rejected" && <StatusCard application={application} />}
        <form onSubmit={submit} className="join-form">
          {fields[kind].map(field => <div className="field" key={field.name}><label htmlFor={field.name}>{field.label}</label><input id={field.name} name={field.name} required maxLength={field.max} /></div>)}
          {kind === "doctor" ? <>
            <div className="field"><label htmlFor="registration_year">Registration year (optional)</label><input id="registration_year" name="registration_year" type="number" min="1900" max={new Date().getFullYear()} /></div>
            <div className="field"><label htmlFor="specialty_name">Specialty (optional)</label><input id="specialty_name" name="specialty_name" maxLength={120} /></div>
          </> : <>
            <div className="field"><label htmlFor="phone_number">Clinic phone, including country code</label><input id="phone_number" name="phone_number" type="tel" required maxLength={16} placeholder="+919876543210" pattern="\+[1-9][0-9]{7,14}" /></div>
            <div className="field"><label htmlFor="email">Clinic contact email</label><input id="email" name="email" type="email" required maxLength={254} /></div>
            <div className="field"><label htmlFor="postal_code">Postal code</label><input id="postal_code" name="postal_code" required inputMode="numeric" maxLength={6} pattern="[1-9][0-9]{5}" /></div>
          </>}
          <label className="join-attestation"><input type="checkbox" name="attestation" required /> {kind === "doctor" ? "I confirm this registration is mine and the information is accurate." : "I am authorized to represent this clinic and the information is accurate."}</label>
          <button className="button" type="submit" disabled={busy}>{busy ? "Submitting…" : application.status === "rejected" ? "Submit corrected application" : "Submit for review"}</button>
        </form>
      </>}
      {error && <p className="message message-error" role="alert">{error} {error.includes("Verify your account email") && <Link href="/account">Verify email</Link>}</p>}
    </section>
  </div>;
}
