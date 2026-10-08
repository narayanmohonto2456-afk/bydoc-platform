"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/components/AuthProvider";
import { administrationUrl, ApiError, apiRequest } from "@/lib/api";

type Role = "patient" | "doctor" | "clinic" | "admin";
type RolesResponse = { roles: Role[]; preferred: Role };
type Appointment = {
  id: string;
  booking_reference: string;
  starts_at: string;
  status: string;
  doctor_name: string;
  clinic_name: string;
};
type PatientOverview = {
  upcoming_count: number;
  open_support_count: number;
  appointments: Appointment[];
  updated_at: string;
};
type DoctorOverview = {
  display_name: string;
  profile_status: string;
  registration_status: string;
  upcoming_appointments_count: number;
  affiliations: { clinic_name: string; status: string; accepts_online_bookings: boolean }[];
  updated_at: string;
};
type ClinicOverview = {
  clinics: { id: string; name: string; status: string; role: string }[];
  selected_clinic_id: string;
  local_date: string;
  timezone: string;
  today_count: number;
  confirmed_count: number;
  checked_in_count: number;
  completed_count: number;
  cancelled_count: number;
  no_show_count: number;
  appointments: (Appointment & { patient_name: string })[];
  updated_at: string;
};
type AdminOverview = {
  account_count: number;
  doctor_count: number;
  clinic_count: number;
  pending_registrations_count: number;
  open_support_count: number;
  updated_at: string;
};
type Overview = PatientOverview | DoctorOverview | ClinicOverview | AdminOverview;

const roleLabels: Record<Role, string> = {
  patient: "Patient",
  doctor: "Doctor",
  clinic: "Clinic",
  admin: "Admin",
};

const roleDescriptions: Record<Role, string> = {
  patient: "Your visits and account at a glance",
  doctor: "Your provider profile and clinic connections",
  clinic: "Today's appointments at your clinic",
  admin: "Platform operations overview",
};

function dateTime(value: string, timeZone?: string) {
  return new Intl.DateTimeFormat("en-IN", { dateStyle: "medium", timeStyle: "short", timeZone }).format(new Date(value));
}

function statusLabel(value: string) {
  return value.replaceAll("_", " ").replace(/^./, letter => letter.toUpperCase());
}

function Stat({ value, label }: { value: number; label: string }) {
  return <div className="dashboard-stat"><strong>{value.toLocaleString("en-IN")}</strong><span>{label}</span></div>;
}

function AppointmentList({ appointments, clinicView = false, timeZone }: { appointments: (Appointment & { patient_name?: string })[]; clinicView?: boolean; timeZone?: string }) {
  if (!appointments.length) return <p className="dashboard-empty">No appointments to show here yet.</p>;
  return <ol className="dashboard-appointments">
    {appointments.map(item => <li key={item.id}>
      <div className="dashboard-appointment-time"><strong>{dateTime(item.starts_at, timeZone)}</strong><span>Booking {item.booking_reference}</span></div>
      <div className="dashboard-appointment-person"><strong>{clinicView ? item.patient_name : item.doctor_name}</strong><span>{clinicView ? item.doctor_name : item.clinic_name}</span></div>
      <span className={`dashboard-status dashboard-status-${item.status}`}>{statusLabel(item.status)}</span>
    </li>)}
  </ol>;
}

function PatientContent({ data }: { data: PatientOverview }) {
  return <>
    <div className="dashboard-stats"><Stat value={data.upcoming_count} label="Upcoming visits" /><Stat value={data.open_support_count} label="Support cases in progress" /></div>
    <section className="panel dashboard-section" aria-labelledby="patient-appointments-heading">
      <div className="dashboard-section-heading"><div><span className="eyebrow">Your care journey</span><h2 id="patient-appointments-heading">Appointments</h2></div><Link className="button" href="/appointments">Find a doctor</Link></div>
      <AppointmentList appointments={data.appointments} />
      <p className="dashboard-note">Appointment status shown here comes from your booking record. <Link href="/account">Update account settings</Link>.</p>
    </section>
  </>;
}

function DoctorContent({ data }: { data: DoctorOverview }) {
  return <>
    <div className="dashboard-stats"><Stat value={data.upcoming_appointments_count} label="Upcoming appointments" /><div className="dashboard-stat"><strong>{statusLabel(data.profile_status)}</strong><span>Profile status</span></div><div className="dashboard-stat"><strong>{statusLabel(data.registration_status)}</strong><span>Registration review</span></div></div>
    <section className="panel dashboard-section" aria-labelledby="doctor-clinics-heading">
      <span className="eyebrow">Dr {data.display_name.replace(/^Dr\.?\s+/i, "")}</span><h2 id="doctor-clinics-heading">Clinic connections</h2>
      {data.affiliations.length ? <ul className="dashboard-connection-list">{data.affiliations.map(item => <li key={item.clinic_name}><strong>{item.clinic_name}</strong><span>{statusLabel(item.status)} affiliation</span><span>{item.accepts_online_bookings ? "Online bookings enabled" : "Online bookings off"}</span></li>)}</ul> : <p className="dashboard-empty">No clinic affiliations have been added to your profile yet.</p>}
      <p className="dashboard-note">Profile and schedule management tools are being built. This overview does not display patient identities.</p>
    </section>
  </>;
}

function ClinicContent({ data, selectedClinicId, onSelectClinic }: { data: ClinicOverview; selectedClinicId: string; onSelectClinic: (id: string) => void }) {
  return <>
    <div className="dashboard-clinic-filter"><label htmlFor="dashboard-clinic">Clinic</label><select id="dashboard-clinic" value={selectedClinicId || data.selected_clinic_id} onChange={event => onSelectClinic(event.target.value)}>{data.clinics.map(item => <option key={item.id} value={item.id}>{item.name} · {statusLabel(item.role)}</option>)}</select><span>{data.local_date} · {data.timezone}</span></div>
    <div className="dashboard-stats"><Stat value={data.today_count} label="Appointments today" /><Stat value={data.confirmed_count} label="Confirmed" /><Stat value={data.checked_in_count} label="Checked in" /><Stat value={data.completed_count} label="Completed" /><Stat value={data.cancelled_count} label="Cancelled" /><Stat value={data.no_show_count} label="No-shows" /></div>
    <section className="panel dashboard-section" aria-labelledby="clinic-appointments-heading">
      <span className="eyebrow">Daily schedule</span><h2 id="clinic-appointments-heading">Today's list</h2>
      <AppointmentList appointments={data.appointments} clinicView timeZone={data.timezone} />
      {data.today_count > data.appointments.length && <p className="dashboard-note">Showing the first {data.appointments.length} appointments in time order.</p>}
      <p className="dashboard-note">Booking, check-in, and schedule change actions are still being built. This list is read only.</p>
    </section>
  </>;
}

function AdminContent({ data }: { data: AdminOverview }) {
  return <>
    <div className="dashboard-stats"><Stat value={data.account_count} label="Accounts" /><Stat value={data.doctor_count} label="Doctor profiles" /><Stat value={data.clinic_count} label="Clinics" /><Stat value={data.pending_registrations_count} label="Registrations pending" /><Stat value={data.open_support_count} label="Support cases open" /></div>
    <section className="panel dashboard-section" aria-labelledby="admin-workspace-heading"><span className="eyebrow">Platform operations</span><h2 id="admin-workspace-heading">Administration</h2><p>Review records and permitted actions in the Django administration site.</p><a className="button" href={administrationUrl()}>Open administration</a><p className="dashboard-note">This overview contains aggregate counts. Actions remain protected by Django permissions.</p></section>
  </>;
}

export function RoleDashboard({ role }: { role: Role }) {
  const { user, loading } = useAuth();
  const [rolesState, setRolesState] = useState<{ userId: string; roles: Role[] } | null>(null);
  const [selectedClinicId, setSelectedClinicId] = useState("");
  const [result, setResult] = useState<{ key: string; data: Overview } | null>(null);
  const [failure, setFailure] = useState<{ key: string; message: string } | null>(null);
  const [attempt, setAttempt] = useState(0);
  const key = `${user?.id ?? ""}:${role}:${selectedClinicId}`;

  useEffect(() => {
    if (!user) return;
    let active = true;
    apiRequest<RolesResponse>("/dashboard/roles/")
      .then(value => { if (active) setRolesState({ userId: user.id, roles: value.roles }); })
      .catch(() => { if (active) setRolesState({ userId: user.id, roles: [role] }); });
    return () => { active = false; };
  }, [user?.id, role]);

  useEffect(() => {
    if (!user) return;
    let active = true;
    const query = role === "clinic" && selectedClinicId ? `?clinic_id=${encodeURIComponent(selectedClinicId)}` : "";
    apiRequest<Overview>(`/dashboard/${role}/${query}`)
      .then(data => { if (active) setResult({ key, data }); })
      .catch(cause => { if (active) setFailure({ key, message: cause instanceof ApiError && cause.status === 403 ? "You do not have access to this dashboard." : "Could not load this dashboard. Please try again." }); });
    return () => { active = false; };
  }, [user?.id, role, selectedClinicId, attempt, key]);

  if (loading) return <div className="wide-shell"><p role="status">Loading your dashboard…</p></div>;
  if (!user) return <div className="form-shell"><div className="panel"><h1>Sign in required</h1><p><Link href="/login">Sign in</Link> to open your dashboard.</p></div></div>;
  const data = result?.key === key ? result.data : null;
  const error = failure?.key === key ? failure.message : "";
  const roles = rolesState?.userId === user.id ? rolesState.roles : [role];

  return <div className="wide-shell dashboard-shell">
    <div className="dashboard-heading"><div><span className="eyebrow">{roleLabels[role]} workspace</span><h1>{role === "patient" ? `Hello, ${user.first_name || user.username}` : `${roleLabels[role]} dashboard`}</h1><p>{roleDescriptions[role]}</p></div><div className="dashboard-heading-mark" aria-hidden="true">✳</div></div>
    <nav className="dashboard-role-nav" aria-label="Your workspaces">{roles.map(item => <Link key={item} href={`/dashboard/${item}`} aria-current={item === role ? "page" : undefined}>{roleLabels[item]}</Link>)}</nav>
    {error ? <div className="panel dashboard-error" role="alert"><p>{error}</p><button className="button button-secondary" onClick={() => { setFailure(null); setResult(null); setAttempt(value => value + 1); }}>Try again</button><Link href="/dashboard">My dashboard</Link></div> : !data ? <div className="panel dashboard-loading" role="status">Loading {roleLabels[role].toLowerCase()} overview…</div> : <>
      {role === "patient" && <PatientContent data={data as PatientOverview} />}
      {role === "doctor" && <DoctorContent data={data as DoctorOverview} />}
      {role === "clinic" && <ClinicContent data={data as ClinicOverview} selectedClinicId={selectedClinicId} onSelectClinic={setSelectedClinicId} />}
      {role === "admin" && <AdminContent data={data as AdminOverview} />}
      <p className="dashboard-updated">Updated {dateTime(data.updated_at)}</p>
    </>}
  </div>;
}
