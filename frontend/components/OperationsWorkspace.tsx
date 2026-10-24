"use client";

import { useCallback, useEffect, useState } from "react";
import { ApiError, apiRequest, postJson } from "@/lib/api";
import { useAuth } from "@/components/AuthProvider";

type Role = "provider" | "support" | "finance" | "schedule" | "delivery";
type Tab = Role | "staff" | "audit";
type Row = Record<string, unknown> & { id?: string; user_id?: string };
type Queue = { results: Row[]; users?: { id: string; username: string; email: string | null }[]; assignees?: { id: string; username: string }[]; recent_webhook_count?: number; gateway_configured?: boolean; webhook_failures?: { event_id: string; event_type: string; error_code: string; failed_count: number; last_seen_at: string }[] };
type SupportDetail = { id: string; reference: string; subject: string; description: string; status: string; events: { id: string; event_type: string; actor_role: string; message: string; created_at: string }[] };
type Action = { label: string; path: string; kind: "reason" | "review" | "status" | "investigation" | "support_status" | "support_reply" | "support_assign" | "escalate" | "grant"; value?: string | boolean };

const labels: Record<Tab, string> = {
  provider: "Provider reviews", support: "Support inbox", finance: "Payments and refunds",
  schedule: "Appointment desk", delivery: "Delivery health", staff: "Staff access", audit: "Audit history",
};
const paths: Record<Tab, string> = {
  provider: "/operations/providers/", support: "/operations/support/", finance: "/operations/payments/",
  schedule: "/operations/appointments/", delivery: "/operations/deliveries/",
  staff: "/operations/staff/", audit: "/operations/audit/",
};
function human(value: unknown) { return String(value ?? "").replaceAll("_", " "); }
function when(value: unknown) { return value ? new Date(String(value)).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" }) : ""; }

export function OperationsWorkspace() {
  const { user } = useAuth();
  const [access, setAccess] = useState<{ roles: Role[]; superuser: boolean } | null>(null);
  const [tab, setTab] = useState<Tab>("provider");
  const [queue, setQueue] = useState<Queue | null>(null);
  const [activeProviders, setActiveProviders] = useState<Row[]>([]);
  const [caseDetails, setCaseDetails] = useState<SupportDetail | null>(null);
  const [action, setAction] = useState<Action | null>(null);
  const [note, setNote] = useState("");
  const [checks, setChecks] = useState({ identity: false, registration: false, duplicate: false });
  const [choice, setChoice] = useState("");
  const [targetUser, setTargetUser] = useState("");
  const [userQuery, setUserQuery] = useState("");
  const [userMatches, setUserMatches] = useState<NonNullable<Queue["users"]>>([]);
  const [searchReference, setSearchReference] = useState("");
  const [activeReference, setActiveReference] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const load = useCallback(async (current: Tab) => {
    setError("");
    try {
      const path = current === "schedule" && activeReference ? `${paths[current]}?reference=${encodeURIComponent(activeReference)}` : paths[current];
      const result = await apiRequest<Queue>(path);
      setQueue(result);
      if (current === "provider") {
        const active = await apiRequest<Queue>("/operations/providers/active/");
        setActiveProviders(active.results);
      }
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "Could not load this queue.");
    }
  }, [activeReference]);

  useEffect(() => {
    if (!user) return;
    apiRequest<{ roles: Role[]; superuser: boolean }>("/operations/me/")
      .then(result => {
        setAccess(result);
        const first = result.roles[0] || (result.superuser ? "staff" : null);
        if (first) setTab(first);
      })
      .catch(() => setError("Could not load operations access."));
  }, [user]);
  useEffect(() => { if (access && (access.roles.includes(tab as Role) || access.superuser)) void load(tab); }, [access, tab, load]);

  function select(next: Tab) { setTab(next); setQueue(null); setAction(null); setCaseDetails(null); setMessage(""); }
  function begin(next: Action) { setAction(next); setNote(""); if (next.kind !== "grant") setChoice(""); setChecks({ identity: false, registration: false, duplicate: false }); setError(""); setMessage(""); }
  async function openCase(id: string) {
    try { setCaseDetails(await apiRequest<SupportDetail>(`/support/cases/${id}/`)); }
    catch (cause) { setError(cause instanceof ApiError ? cause.message : "Could not open this case."); }
  }
  async function searchUsers() {
    if (userQuery.trim().length < 2) { setError("Enter at least two characters to find an account."); return; }
    try {
      const result = await apiRequest<Queue>(`/operations/staff/?search=${encodeURIComponent(userQuery.trim())}`);
      setUserMatches(result.users || []);
      setTargetUser(""); setError("");
    } catch (cause) { setError(cause instanceof ApiError ? cause.message : "Could not search accounts."); }
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!action || !note.trim()) return;
    setBusy(true); setError("");
    try {
      let body: Record<string, unknown> = { note: note.trim() };
      if (action.kind === "review") body = { ...body, approve: action.value === true, checks };
      if (action.kind === "status") body.suspend = action.value === true;
      if (action.kind === "status") body.checks = checks;
      if (action.kind === "investigation") body.resolved = action.value === true;
      if (action.kind === "support_status") body = { new_status: action.value, message: note.trim(), resolution_summary: action.value === "resolved" ? note.trim() : "" };
      if (action.kind === "support_reply") body = { message: note.trim() };
      if (action.kind === "support_assign") body = { assigned_to_id: choice, note: note.trim() };
      if (action.kind === "escalate") body.priority = choice;
      if (action.kind === "grant") body = { note: note.trim(), role: choice, active: action.value === true };
      await postJson(action.path, body);
      setAction(null); setMessage(`${action.label} completed.`);
      await load(tab);
      if (tab === "support" && caseDetails) await openCase(caseDetails.id);
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "Action failed. Please try again.");
    } finally { setBusy(false); }
  }

  if (!user || !access || (!access.roles.length && !access.superuser)) return null;
  const tabs: Tab[] = [...access.roles, ...(access.superuser ? ["staff" as Tab, "audit" as Tab] : [])];
  const rows = queue?.results || [];
  const actionFor = (row: Row, label: string, suffix: string, kind: Action["kind"], value?: Action["value"]) =>
    begin({ label, path: suffix, kind, value });

  return <section className="wide-shell operations" aria-labelledby="operations-title">
    <div className="operations-heading"><div><span className="eyebrow">Protected workspace</span><h2 id="operations-title">Operations queues</h2><p>Review exceptions and record every decision with a reason.</p></div><button className="button button-secondary" onClick={() => void load(tab)}>Refresh</button></div>
    <nav className="operations-tabs" aria-label="Operations queues">{tabs.map(item => <button key={item} className={tab === item ? "is-active" : ""} aria-current={tab === item ? "page" : undefined} onClick={() => select(item)}>{labels[item]}</button>)}</nav>
    {error && <p className="operations-error" role="alert">{error}</p>}
    {message && <p className="operations-success" role="status">{message}</p>}
    {!queue ? <div className="panel operations-empty">Loading {labels[tab].toLowerCase()}…</div> : <>
      {tab === "finance" && <p className="operations-hint">Razorpay: {queue.gateway_configured ? "configured" : "not configured"} · Webhooks received in 24 hours: {queue.recent_webhook_count ?? 0}. Payment status changes only after provider verification.</p>}
      {tab === "finance" && !!queue.webhook_failures?.length && <section className="panel operations-card"><h3>Webhook failures</h3><p className="operations-hint">These signed events failed processing. Razorpay can retry them; investigate the related payment and reconcile with the provider.</p><ul>{queue.webhook_failures.map(item => <li key={item.event_id}>{item.event_type || "Unknown event"} · {item.error_code} · {item.failed_count} attempt(s) · {when(item.last_seen_at)}</li>)}</ul></section>}
      {tab === "support" && <p className="operations-hint">Response targets: high 4 hours, normal 24 hours, low 48 hours. The target shown uses case creation time.</p>}
      {tab === "schedule" && <form className="operations-search" onSubmit={event => { event.preventDefault(); setActiveReference(searchReference.trim()); }}><label>Find booking by reference<input value={searchReference} onChange={event => setSearchReference(event.target.value)} placeholder="Booking UUID" /></label><button className="button" type="submit">Find</button><button className="button button-secondary" type="button" onClick={() => { setSearchReference(""); setActiveReference(""); }}>Clear</button></form>}
      {tab === "staff" && <form className="panel operations-grant" onSubmit={event => { event.preventDefault(); if (targetUser && choice) begin({ label: "Grant access", path: `/operations/staff/${targetUser}/grant/`, kind: "grant", value: true }); }}><h3>Grant staff access</h3><label>Find account<input value={userQuery} onChange={event => { setUserQuery(event.target.value); setUserMatches([]); setTargetUser(""); }} placeholder="Username or email" minLength={2} maxLength={100} /></label><button className="button button-secondary" type="button" onClick={() => void searchUsers()}>Search</button><label>Account<select value={targetUser} onChange={event => setTargetUser(event.target.value)} required><option value="">Select account</option>{userMatches.map(person => <option key={person.id} value={person.id}>{person.username}{person.email ? ` · ${person.email}` : ""}</option>)}</select></label><label>Role<select value={choice} onChange={event => setChoice(event.target.value)} required><option value="">Select role</option>{(Object.keys(labels).slice(0, 5) as Role[]).map(role => <option key={role} value={role}>{labels[role]}</option>)}</select></label><button className="button" type="submit">Continue</button></form>}
      {!rows.length && <div className="panel operations-empty">No records in this queue.</div>}
      <div className="operations-list">{rows.map((row, index) => {
        const id = String(row.id || row.user_id || index);
        const title = tab === "provider" ? row.name : tab === "finance" || tab === "schedule" ? `Booking ${row.booking_reference}` : tab === "support" ? row.subject : tab === "delivery" ? `${human(row.channel)} · ${human(row.category)}` : tab === "staff" ? row.username : `${row.action} · ${row.actor}`;
        return <article className="panel operations-card" key={`${tab}-${id}-${index}`}><div className="operations-card-top"><div><strong>{String(title || id)}</strong><span>{tab === "provider" ? `${human(row.kind)} · ${row.applicant}` : tab === "support" ? `${row.reference} · ${human(row.priority)}` : tab === "finance" ? `₹${(Number(row.amount_paise) / 100).toFixed(2)}` : tab === "schedule" ? `${row.clinic} · ${row.doctor}` : tab === "staff" ? `Role: ${human(row.role)}` : tab === "audit" ? `${row.subject_type} · ${row.subject_id}` : `Attempts: ${row.attempt_count}/${row.max_attempts}`}</span></div><span className="dashboard-status">{human(row.status || (row.active === undefined ? "" : row.active ? "active" : "revoked"))}</span></div>
          <p className="operations-meta">{when(row.submitted_at || row.created_at || row.starts_at || row.scheduled_for || row.updated_at)}{row.response_due_at ? ` · Response due ${when(row.response_due_at)}${row.overdue ? " · OVERDUE" : ""}` : ""}</p>
          {tab === "provider" && <p className="operations-meta">{String(row.authority || "")} · Registration {String(row.registration_number || "")}{row.postal_code ? ` · ${row.district} ${row.postal_code}` : ""}{row.review_note ? ` · Review: ${row.review_note}` : ""}</p>}
          {tab === "finance" && <p className="operations-meta">{String(row.last_error || "No provider error recorded")}{row.investigation && typeof row.investigation === "object" ? ` · Investigation: ${String((row.investigation as Record<string, unknown>).note)}` : ""}</p>}
          {tab === "support" && <p className="operations-meta">Assigned: {row.assigned_to && typeof row.assigned_to === "object" ? String((row.assigned_to as Record<string, unknown>).username) : "unassigned"}</p>}
          {tab === "schedule" && <p className="operations-meta">Payment: {human(row.payment_status || "pay at clinic")} · Open support cases: {String(row.open_support_count ?? 0)}</p>}
          {tab === "delivery" && <p className="operations-meta">{human(row.last_error_code || "No error code")}</p>}
          {tab === "audit" && <p className="operations-meta">{String(row.note || "No note")}</p>}
          <div className="operations-actions">
            {tab === "provider" && row.status === "pending" && <><button onClick={() => actionFor(row, "Approve provider", `/operations/providers/${row.kind}/${id}/review/`, "review", true)}>Approve</button><button onClick={() => actionFor(row, "Reject provider", `/operations/providers/${row.kind}/${id}/review/`, "review", false)}>Reject</button></>}
            {tab === "finance" && <><button onClick={() => actionFor(row, "Reconcile with Razorpay", `/operations/payments/${id}/reconcile/`, "reason")}>Reconcile</button><button onClick={() => actionFor(row, "Open investigation", `/operations/payments/${id}/investigation/`, "investigation", false)}>Investigate</button><button onClick={() => actionFor(row, "Resolve investigation", `/operations/payments/${id}/investigation/`, "investigation", true)}>Mark reviewed</button></>}
            {tab === "support" && <><button onClick={() => void openCase(id)}>View conversation</button><button onClick={() => actionFor(row, "Reply", `/support/cases/${id}/comments/`, "support_reply")}>Reply</button><button onClick={() => actionFor(row, "Assign case", `/support/staff/cases/${id}/assign/`, "support_assign")}>Assign</button><button onClick={() => actionFor(row, "Escalate case", `/operations/support/${id}/escalate/`, "escalate")}>Priority</button>{["in_progress", "waiting_for_user", "resolved", "closed"].map(next => <button key={next} onClick={() => actionFor(row, `Set ${human(next)}`, `/support/staff/cases/${id}/status/`, "support_status", next)}>{human(next)}</button>)}</>}
            {tab === "schedule" && row.status === "confirmed" && <button onClick={() => actionFor(row, "Cancel appointment", `/operations/appointments/${id}/cancel/`, "reason")}>Cancel and refund if paid</button>}
            {tab === "delivery" && row.status === "failed" && <button onClick={() => actionFor(row, "Retry delivery", `/operations/deliveries/${id}/retry/`, "reason")}>Retry</button>}
            {tab === "staff" && <button onClick={() => { setChoice(String(row.role)); actionFor(row, "Revoke access", `/operations/staff/${row.user_id}/grant/`, "grant", false); }}>Revoke</button>}
          </div>
        </article>;
      })}</div>
      {tab === "support" && caseDetails && <section className="panel operations-detail" aria-label={`Case ${caseDetails.reference}`}><div className="operations-card-top"><h3>{caseDetails.reference}: {caseDetails.subject}</h3><button className="button button-secondary" onClick={() => setCaseDetails(null)}>Close</button></div><p>{caseDetails.description}</p><ol>{caseDetails.events.map(event => <li key={event.id}><strong>{human(event.actor_role)} · {human(event.event_type)}</strong><span>{when(event.created_at)}</span>{event.message && <p>{event.message}</p>}</li>)}</ol></section>}
      {tab === "provider" && <><h3 className="operations-subheading">Active and suspended providers</h3><div className="operations-list">{activeProviders.map(row => <article className="panel operations-card" key={String(row.id)}><div className="operations-card-top"><strong>{String(row.name)} · {human(row.kind)}</strong><span className="dashboard-status">{human(row.status)}</span></div><div className="operations-actions"><button onClick={() => actionFor(row, row.status === "active" ? "Suspend provider" : "Reactivate provider", `/operations/providers/${row.kind}/${row.id}/status/`, "status", row.status === "active")}>{row.status === "active" ? "Suspend" : "Reactivate"}</button></div></article>)}</div></>}
    </>}
    {action && <div className="operations-modal-backdrop" role="presentation"><form className="panel operations-modal" role="dialog" aria-modal="true" onSubmit={submit} aria-label={action.label}><h3>{action.label}</h3><p>Record the reason for this change. Keep clinical details and payment credentials out of notes.</p>
      {(action.kind === "review" || (action.kind === "status" && action.value === false)) && <fieldset><legend>Verification checklist</legend>{(Object.keys(checks) as (keyof typeof checks)[]).map(key => <label key={key}><input type="checkbox" checked={checks[key]} onChange={event => setChecks(previous => ({ ...previous, [key]: event.target.checked }))} /> {key === "identity" ? "Applicant identity checked" : key === "registration" ? "Registration details checked" : "Duplicates checked"}</label>)}</fieldset>}
      {action.kind === "support_assign" && <label>Assignee<select required value={choice} onChange={event => setChoice(event.target.value)}><option value="">Select staff member</option>{queue?.assignees?.map(person => <option key={person.id} value={person.id}>{person.username}</option>)}</select></label>}
      {action.kind === "escalate" && <label>Priority<select required value={choice} onChange={event => setChoice(event.target.value)}><option value="">Select priority</option><option value="high">High</option><option value="normal">Normal</option><option value="low">Low</option></select></label>}
      {action.kind === "grant" && <label>Role<select required value={choice} onChange={event => setChoice(event.target.value)}><option value="">Select role</option>{(Object.keys(labels).slice(0, 5) as Role[]).map(role => <option key={role} value={role}>{labels[role]}</option>)}</select></label>}
      <label>Reason or message<textarea value={note} onChange={event => setNote(event.target.value)} maxLength={action.kind === "support_reply" || action.kind === "support_status" ? 3000 : action.kind === "reason" ? 250 : 500} required rows={4} /></label><div className="operations-actions"><button className="button" type="submit" disabled={busy || ((action.kind === "review" && action.value === true || action.kind === "status" && action.value === false) && !Object.values(checks).every(Boolean))}>{busy ? "Working…" : "Confirm"}</button><button className="button button-secondary" type="button" onClick={() => setAction(null)} disabled={busy}>Cancel</button></div></form></div>}
  </section>;
}
