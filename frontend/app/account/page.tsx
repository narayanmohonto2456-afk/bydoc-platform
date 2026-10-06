"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/components/AuthProvider";
import { apiRequest, PatientProfile, postJson } from "@/lib/api";
import { PasswordField } from "@/components/PasswordField";

export default function AccountPage() {
  const router = useRouter();
  const { user, loading, logout, refresh } = useAuth();
  const [profile, setProfile] = useState<PatientProfile | null>(null);
  const [savedProfile, setSavedProfile] = useState<PatientProfile | null>(null);
  const [profileError, setProfileError] = useState("");
  const [profileSaved, setProfileSaved] = useState(false);
  const [profileBusy, setProfileBusy] = useState(false);
  const [address, setAddress] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [verifyError, setVerifyError] = useState("");
  const [verifyDone, setVerifyDone] = useState(false);
  const [verifyBusy, setVerifyBusy] = useState(false);
  const [logoutError, setLogoutError] = useState("");

  useEffect(() => {
    if (!user) return;
    apiRequest<PatientProfile>("/auth/profile/")
      .then(result => { setProfile(result); setSavedProfile(result); })
      .catch(cause => setProfileError(cause instanceof Error ? cause.message : "Could not load your profile."));
  }, [user?.id]);

  const profileDirty = profile !== null && savedProfile !== null && JSON.stringify(profile) !== JSON.stringify(savedProfile);

  function change<K extends keyof PatientProfile>(key: K, value: PatientProfile[K]) {
    setProfile(current => current ? { ...current, [key]: value } : current);
    setProfileSaved(false);
  }

  async function saveProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!profile || !profileDirty) return;
    setProfileError("");
    setProfileSaved(false);
    setProfileBusy(true);
    try {
      const saved = await apiRequest<PatientProfile>("/auth/profile/", {
        method: "PATCH",
        body: JSON.stringify({ ...profile, phone_number: profile.phone_number || "" }),
      });
      setProfile(saved);
      setSavedProfile(saved);
      setProfileSaved(true);
      await refresh();
    } catch (cause) {
      setProfileError(cause instanceof Error ? cause.message : "Could not save your profile.");
    } finally {
      setProfileBusy(false);
    }
  }

  async function requestVerification(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setVerifyError("");
    setVerifyDone(false);
    setVerifyBusy(true);
    try {
      await postJson("/auth/email/verify/request/", { address, current_password: currentPassword });
      setCurrentPassword("");
      setVerifyDone(true);
    } catch (cause) {
      setVerifyError(cause instanceof Error ? cause.message : "Could not request verification.");
    } finally {
      setVerifyBusy(false);
    }
  }

  async function signOut() {
    setLogoutError("");
    try {
      await logout();
      router.replace("/");
    } catch (cause) {
      setLogoutError(cause instanceof Error ? cause.message : "Could not sign out.");
    }
  }

  if (loading) return <div className="wide-shell"><p role="status">Loading your account…</p></div>;
  if (!user) return <div className="form-shell"><div className="panel"><h1>Sign in required</h1><p>Please <Link href="/login">sign in</Link> to see your account.</p></div></div>;

  return <div className="wide-shell">
    <div className="account-heading"><div><span className="eyebrow">My account</span><h1>Hello, {user.first_name || user.username}</h1></div><button className="button button-secondary" onClick={signOut}>Sign out</button></div>
    {logoutError && <div className="message message-error" role="alert">{logoutError}</div>}
    <div className="account-grid">
      <section className="panel" aria-labelledby="profile-heading">
        <h2 id="profile-heading">Patient profile</h2><p>These details help keep your appointment information accurate.</p>
        {profileError && <div className="message message-error" role="alert">{profileError}</div>}
        {profileSaved && <div className="message message-success" role="status">Profile saved.</div>}
        {!profile ? <p role="status">Loading profile…</p> : <form onSubmit={saveProfile}>
          <div className="field"><label htmlFor="first-name">First name</label><input id="first-name" autoComplete="given-name" maxLength={150} value={profile.first_name} onChange={event => change("first_name", event.target.value)} /></div>
          <div className="field"><label htmlFor="last-name">Last name</label><input id="last-name" autoComplete="family-name" maxLength={150} value={profile.last_name} onChange={event => change("last_name", event.target.value)} /></div>
          <div className="field"><label htmlFor="phone">Phone number</label><input id="phone" type="tel" autoComplete="tel" placeholder="+919876543210" value={profile.phone_number || ""} onChange={event => change("phone_number", event.target.value)} /><span className="field-hint">Use international format, beginning with + and the country code. This number is not yet verified.</span></div>
          <div className="field"><label htmlFor="birth-date">Date of birth</label><input id="birth-date" type="date" max={new Date().toISOString().slice(0, 10)} value={profile.date_of_birth || ""} onChange={event => change("date_of_birth", event.target.value || null)} /></div>
          <div className="field"><label htmlFor="gender">Gender (optional)</label><select id="gender" value={profile.gender} onChange={event => change("gender", event.target.value)}><option value="">Prefer not to provide</option><option value="woman">Woman</option><option value="man">Man</option><option value="non_binary">Non-binary</option><option value="prefer_not_to_say">Prefer not to say</option></select></div>
          <div className="divider" /><h3>Emergency contact (optional)</h3><p>Provide both the name and phone number, or leave both empty.</p>
          <div className="field"><label htmlFor="emergency-name">Contact name</label><input id="emergency-name" maxLength={150} value={profile.emergency_contact_name} onChange={event => change("emergency_contact_name", event.target.value)} /></div>
          <div className="field"><label htmlFor="emergency-phone">Contact phone</label><input id="emergency-phone" type="tel" placeholder="+919876543211" value={profile.emergency_contact_phone} onChange={event => change("emergency_contact_phone", event.target.value)} /></div>
          <div className="form-actions"><button className="button" disabled={profileBusy || !profileDirty}>{profileBusy ? "Saving…" : "Save changes"}</button><button className="button button-secondary" type="button" disabled={profileBusy || !profileDirty} onClick={() => { setProfile(savedProfile); setProfileError(""); }}>Discard changes</button>{profileDirty && <span className="unsaved-label" role="status">Unsaved changes</span>}</div>
        </form>}
      </section>
      <section className="panel" aria-labelledby="email-heading">
        <h2 id="email-heading">Recovery email</h2><p>Verify an email address so you can reset your password if needed. Your current password is required to add or replace it.</p>
        {verifyError && <div className="message message-error" role="alert">{verifyError}</div>}
        {verifyDone && <div className="message message-success" role="status">Verification requested. Open the link sent to your email address within 30 minutes.</div>}
        <form onSubmit={requestVerification}>
          <div className="field"><label htmlFor="address">Email address</label><input id="address" type="email" autoComplete="email" required value={address} onChange={event => setAddress(event.target.value)} /></div>
          <PasswordField id="current-password" label="Current password" autoComplete="current-password" value={currentPassword} onChange={setCurrentPassword} />
          <button className="button" disabled={verifyBusy}>{verifyBusy ? "Submitting…" : "Send verification link"}</button>
        </form>
      </section>
    </div>
  </div>;
}
