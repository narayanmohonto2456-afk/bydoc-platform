"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/components/AuthProvider";
import { ApiError, apiRequest, postJson } from "@/lib/api";

type Provider = {
  id: string; doctor_id: string; doctor_name: string; specialty: string | null;
  languages: string[]; clinic_id: string; clinic_name: string; locality: string;
  district: string; state: string; address: string; timezone: string;
  consultation_fee: string | null; currency_code: string;
  fee_updated_at: string | null; schedule_updated_at: string | null;
};
type Page<T> = { results: T[]; next: string | null; count: number };
type Slot = {
  id: string; doctor_id: string; doctor_name: string; clinic_id: string;
  clinic_name: string; starts_at: string; ends_at: string;
  consultation_fee: string | null; currency_code: string;
};
type Hold = { slot_id: string; hold_token: string; hold_expires_at: string };
type Appointment = Slot & {
  booking_reference: string; status: string; created_at: string;
};

function localDate(timeZone: string): string {
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone, year: "numeric", month: "2-digit", day: "2-digit",
  }).formatToParts(new Date());
  const find = (type: string) => parts.find(part => part.type === type)?.value ?? "";
  return `${find("year")}-${find("month")}-${find("day")}`;
}

function visitTime(value: string, timeZone: string): string {
  return new Intl.DateTimeFormat("en-IN", {
    timeZone, dateStyle: "medium", timeStyle: "short",
  }).format(new Date(value));
}

function fee(value: string | null, currency: string): string {
  if (value === null) return "Ask the clinic for the consultation fee";
  try {
    return new Intl.NumberFormat("en-IN", { style: "currency", currency }).format(Number(value));
  } catch {
    return `${currency} ${value}`;
  }
}

export default function AppointmentsPage() {
  const { user, loading: authLoading } = useAuth();
  const [query, setQuery] = useState("");
  const [district, setDistrict] = useState("");
  const [search, setSearch] = useState({ query: "", district: "" });
  const [providers, setProviders] = useState<Provider[]>([]);
  const [nextPage, setNextPage] = useState<string | null>(null);
  const [providerLoading, setProviderLoading] = useState(true);
  const [providerError, setProviderError] = useState("");
  const [selected, setSelected] = useState<Provider | null>(null);
  const [date, setDate] = useState("");
  const [slots, setSlots] = useState<Slot[]>([]);
  const [slotLoading, setSlotLoading] = useState(false);
  const [slotError, setSlotError] = useState("");
  const [chosen, setChosen] = useState<Slot | null>(null);
  const [hold, setHold] = useState<Hold | null>(null);
  const [requestId, setRequestId] = useState("");
  const [booking, setBooking] = useState<Appointment | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [actionError, setActionError] = useState("");

  useEffect(() => {
    const clinicName = new URLSearchParams(window.location.search).get("q")?.trim();
    if (clinicName) {
      setQuery(clinicName);
      setSearch({ query: clinicName, district: "" });
    }
  }, []);

  useEffect(() => {
    let active = true;
    const params = new URLSearchParams();
    if (search.query) params.set("q", search.query);
    if (search.district) params.set("district", search.district);
    apiRequest<Page<Provider>>(`/appointments/providers/?${params}`)
      .then(data => { if (active) { setProviders(data.results); setNextPage(data.next); setProviderError(""); } })
      .catch(error => { if (active) setProviderError(error instanceof Error ? error.message : "Could not load doctors."); })
      .finally(() => { if (active) setProviderLoading(false); });
    return () => { active = false; };
  }, [search]);

  useEffect(() => {
    if (!selected || !date) return;
    let active = true;
    const params = new URLSearchParams({ clinic_id: selected.clinic_id, doctor_id: selected.doctor_id, date });
    apiRequest<Slot[]>(`/appointments/slots/?${params}`)
      .then(data => { if (active) { setSlots(data); setSlotError(""); } })
      .catch(error => { if (active) { setSlots([]); setSlotError(error instanceof Error ? error.message : "Could not load times."); } })
      .finally(() => { if (active) setSlotLoading(false); });
    return () => { active = false; };
  }, [selected, date]);

  const selectProvider = useCallback((provider: Provider) => {
    setSelected(provider);
    setDate(localDate(provider.timezone));
    setSlots([]);
    setSlotLoading(true);
    setChosen(null);
    setHold(null);
    setRequestId("");
    setBooking(null);
    setActionError("");
  }, []);

  function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setProviderLoading(true);
    setSelected(null);
    setSearch({ query: query.trim(), district: district.trim() });
  }

  async function loadMore() {
    if (!nextPage) return;
    setProviderLoading(true);
    try {
      const url = new URL(nextPage);
      const data = await apiRequest<Page<Provider>>(`/appointments/providers/${url.search}`);
      setProviders(current => [...current, ...data.results]);
      setNextPage(data.next);
    } catch (error) {
      setProviderError(error instanceof Error ? error.message : "Could not load more doctors.");
    } finally {
      setProviderLoading(false);
    }
  }

  async function holdChosenSlot() {
    if (!chosen || !user) return;
    setActionLoading(true);
    setActionError("");
    try {
      const held = await postJson<Hold>(`/appointments/slots/${chosen.id}/hold/`, {});
      setHold(held);
      setRequestId(crypto.randomUUID());
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Could not hold this time.");
      setChosen(null);
      setSlotLoading(true);
      const params = new URLSearchParams({ clinic_id: selected!.clinic_id, doctor_id: selected!.doctor_id, date });
      apiRequest<Slot[]>(`/appointments/slots/?${params}`).then(setSlots).finally(() => setSlotLoading(false));
    } finally {
      setActionLoading(false);
    }
  }

  async function confirmBooking() {
    if (!chosen || !hold || !requestId) return;
    setActionLoading(true);
    setActionError("");
    try {
      const result = await postJson<Appointment>(`/appointments/slots/${chosen.id}/book/`, {
        hold_token: hold.hold_token, booking_request_id: requestId,
      });
      if (result.status !== "confirmed") throw new Error("Booking status could not be confirmed. Check your appointments before retrying.");
      setBooking(result);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Could not confirm the booking.";
      setActionError(error instanceof ApiError && error.status === 409
        ? `${message} Choose another available time.`
        : `${message} If the request was interrupted, retry with the same booking request or check your dashboard.`);
      if (error instanceof ApiError && error.status === 409) setHold(null);
    } finally {
      setActionLoading(false);
    }
  }

  return <div className="wide-shell booking-shell">
    <header className="booking-heading"><span className="eyebrow">Plan your visit</span><h1>Find care and book a time</h1><p>See a verified doctor, clinic, available time, and declared consultation fee before you confirm.</p><Link href="/clinics/nearby">Explore clinics near me →</Link></header>
    <form className="panel booking-search" onSubmit={submitSearch}>
      <div className="field"><label htmlFor="care-search">Doctor, specialty, or clinic</label><input id="care-search" value={query} onChange={event => setQuery(event.target.value)} maxLength={100} placeholder="e.g. cardiology or clinic name" /></div>
      <div className="field"><label htmlFor="care-district">District</label><input id="care-district" value={district} onChange={event => setDistrict(event.target.value)} maxLength={120} placeholder="e.g. Kolkata" /></div>
      <button className="button" type="submit">Search</button>
    </form>
    {providerError && <p role="alert" className="message message-error">{providerError}</p>}
    {providerLoading && !providers.length ? <p role="status">Loading available doctors…</p> : !providers.length && !providerError ? <p className="dashboard-empty">{search.query || search.district ? "No verified doctors match this search. Try a different name or district." : "No verified doctors are available for online booking yet."}</p> : <div className="booking-layout">
      <section aria-labelledby="provider-heading"><h2 id="provider-heading">Doctors and clinics</h2><ul className="provider-list">{providers.map(provider => <li key={provider.id}><button type="button" className={`provider-card${selected?.id === provider.id ? " is-selected" : ""}`} onClick={() => selectProvider(provider)} aria-pressed={selected?.id === provider.id}>
        <span className="provider-name">{provider.doctor_name}</span><span>{provider.specialty || "Specialty not listed"} · Verified registration</span>
        <strong>{provider.clinic_name}</strong><span>{provider.locality}, {provider.district}, {provider.state}</span>
        <span>{fee(provider.consultation_fee, provider.currency_code)} · Pay at clinic</span>
      </button></li>)}</ul>{nextPage && <button className="button button-secondary" type="button" onClick={loadMore} disabled={providerLoading}>Load more doctors</button>}</section>
      <section className="panel booking-detail" aria-labelledby="booking-detail-heading">
        {!selected ? <><h2 id="booking-detail-heading">Choose a doctor</h2><p>Select a doctor and clinic to see available times.</p></> : <>
          <span className="eyebrow">Verified provider</span><h2 id="booking-detail-heading">{selected.doctor_name}</h2>
          <p><strong>{selected.clinic_name}</strong><br />{selected.address}, {selected.locality}, {selected.district}</p>
          {selected.languages.length > 0 && <p>Languages: {selected.languages.join(", ")}</p>}
          <p className="booking-fee">Consultation fee: <strong>{fee(selected.consultation_fee, selected.currency_code)}</strong><br /><small>Pay the provider directly at the clinic. The fee may change; confirm with the clinic if needed.</small></p>
          {selected.schedule_updated_at && <p className="dashboard-note">Schedule last updated {visitTime(selected.schedule_updated_at, selected.timezone)}</p>}
          {booking ? <div className="message message-success" role="status"><strong>Appointment confirmed</strong><p>{visitTime(booking.starts_at, selected.timezone)} at {booking.clinic_name}</p><p>Booking reference: {booking.booking_reference}</p><Link href="/dashboard/patient">View my dashboard</Link></div> : <>
            <div className="field"><label htmlFor="appointment-date">Choose a date</label><input id="appointment-date" type="date" value={date} min={localDate(selected.timezone)} onChange={event => { setDate(event.target.value); setSlotLoading(Boolean(event.target.value)); setSlots([]); setChosen(null); setHold(null); setActionError(""); }} /></div>
            {slotError && <p className="message message-error" role="alert">{slotError}</p>}
            {!date ? <p className="dashboard-empty">Choose a date to see available times.</p> : slotLoading ? <p role="status">Checking available times…</p> : !slots.length && !slotError ? <p className="dashboard-empty">No open times on this date. Try another date.</p> : <div role="group" aria-label="Available appointment times" className="slot-grid">{slots.map(slot => <button key={slot.id} type="button" className={chosen?.id === slot.id ? "is-selected" : ""} disabled={!!hold} aria-pressed={chosen?.id === slot.id} onClick={() => { setChosen(slot); setActionError(""); }}>{new Intl.DateTimeFormat("en-IN", { timeZone: selected.timezone, hour: "numeric", minute: "2-digit" }).format(new Date(slot.starts_at))}</button>)}</div>}
            {chosen && <div className="booking-review"><h3>Review your visit</h3><p>{visitTime(chosen.starts_at, selected.timezone)}<br />{selected.doctor_name} at {selected.clinic_name}</p><p>Consultation fee: <strong>{fee(chosen.consultation_fee, chosen.currency_code)}</strong> · Pay at clinic</p>
              {!user && !authLoading ? <p><Link href="/login">Sign in</Link> to book this time.</p> : !hold ? <button type="button" className="button" disabled={actionLoading || authLoading} onClick={holdChosenSlot}>{actionLoading ? "Holding time…" : "Continue to confirmation"}</button> : <><p className="dashboard-note">Held until {visitTime(hold.hold_expires_at, selected.timezone)}. Leaving this page lets the hold expire.</p><button type="button" className="button" disabled={actionLoading} onClick={confirmBooking}>{actionLoading ? "Confirming…" : "Confirm appointment"}</button></>}
            </div>}
            {actionError && <p className="message message-error" role="alert">{actionError}</p>}
          </>}
        </>}
      </section>
    </div>}
    <p className="site-note">BYdoc does not provide emergency care or medical advice. For emergencies, contact local emergency services.</p>
  </div>;
}
