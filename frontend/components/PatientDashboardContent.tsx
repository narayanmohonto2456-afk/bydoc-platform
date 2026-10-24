import Link from "next/link";
import { AppointmentPayment } from "@/components/AppointmentPayment";

type PatientAppointment = {
  id: string;
  booking_reference: string;
  starts_at: string;
  status: string;
  doctor_name: string;
  clinic_name: string;
};

export type PatientOverview = {
  upcoming_count: number;
  open_support_count: number;
  next_appointment: PatientAppointment | null;
  appointments: PatientAppointment[];
  updated_at: string;
};

function visitDate(value: string) {
  return new Intl.DateTimeFormat("en-IN", { dateStyle: "full", timeStyle: "short" }).format(new Date(value));
}

function datePart(value: string, part: "day" | "month") {
  return new Intl.DateTimeFormat("en-IN", { [part]: part === "month" ? "short" : "numeric" }).format(new Date(value));
}

function statusLabel(value: string) {
  return value.replaceAll("_", " ").replace(/^./, letter => letter.toUpperCase());
}

function NextVisit({ appointment }: { appointment: PatientAppointment | null }) {
  return <section className="panel patient-next" aria-labelledby="patient-next-heading">
    <div className="patient-next-top"><span className="eyebrow">Your next visit</span><span className="patient-next-count">BYdoc appointments</span></div>
    {appointment ? <>
      <div className="patient-next-main">
        <div className="patient-date-tile" aria-hidden="true"><span>{datePart(appointment.starts_at, "month")}</span><strong>{datePart(appointment.starts_at, "day")}</strong></div>
        <div className="patient-next-copy">
          <h2 id="patient-next-heading">Your appointment is coming up</h2>
          <p className="patient-next-doctor">{appointment.doctor_name}</p>
          <p className="patient-next-clinic">{appointment.clinic_name}</p>
          <p className="patient-next-time">{visitDate(appointment.starts_at)}</p>
        </div>
      </div>
      <div className="patient-next-meta"><span className={`dashboard-status dashboard-status-${appointment.status}`}>{statusLabel(appointment.status)}</span><span>Booking {appointment.booking_reference}</span></div>
      <div className="patient-next-payment"><AppointmentPayment appointmentId={appointment.id} /></div>
    </> : <div className="patient-next-empty">
      <h2 id="patient-next-heading">No visit on your calendar</h2>
      <p>Find an available doctor and choose a time that works for you.</p>
      <Link className="button" href="/appointments">Find a doctor <span aria-hidden="true">↗</span></Link>
    </div>}
  </section>;
}

function VisitList({ appointments }: { appointments: PatientAppointment[] }) {
  if (!appointments.length) return <div className="patient-history-empty"><p>No other bookings to show yet.</p><Link href="/appointments">Explore available appointments</Link></div>;
  return <ol className="patient-visit-list">{appointments.map(appointment => <li key={appointment.id}>
    <div className="patient-visit-date" aria-hidden="true"><strong>{datePart(appointment.starts_at, "day")}</strong><span>{datePart(appointment.starts_at, "month")}</span></div>
    <div className="patient-visit-info"><strong>{appointment.doctor_name}</strong><span>{appointment.clinic_name}</span><time dateTime={appointment.starts_at}>{visitDate(appointment.starts_at)}</time><small>Booking {appointment.booking_reference}</small></div>
    <span className={`dashboard-status dashboard-status-${appointment.status}`}>{statusLabel(appointment.status)}</span>
    <details className="patient-visit-payment"><summary>Payment details</summary><AppointmentPayment appointmentId={appointment.id} /></details>
  </li>)}</ol>;
}

export function PatientDashboardContent({ data }: { data: PatientOverview }) {
  return <div className="patient-dashboard">
    <div className="patient-dashboard-grid">
      <NextVisit appointment={data.next_appointment} />
      <aside className="patient-sidebar" aria-label="Care shortcuts">
        <div className="patient-sidebar-heading"><span className="eyebrow">At a glance</span><h2>Your care, in one place</h2></div>
        <div className="patient-sidebar-stat"><strong>{data.upcoming_count.toLocaleString("en-IN")}</strong><span>Upcoming {data.upcoming_count === 1 ? "visit" : "visits"}</span></div>
        <div className="patient-sidebar-stat"><strong>{data.open_support_count.toLocaleString("en-IN")}</strong><span>Open support {data.open_support_count === 1 ? "request" : "requests"}</span></div>
        <div className="patient-sidebar-links"><Link href="/appointments">{data.next_appointment || data.appointments.length ? "Book another visit" : "Book a visit"} <span aria-hidden="true">↗</span></Link><Link href="/clinics/nearby">Find nearby clinics <span aria-hidden="true">↗</span></Link><Link href="/account">Account settings <span aria-hidden="true">↗</span></Link></div>
        <p>Need help with a booking? Open BYdoc help at the bottom of the page.</p>
      </aside>
    </div>
    <section className="panel patient-history" aria-labelledby="patient-history-heading">
      <div className="patient-history-heading"><div><span className="eyebrow">Your activity</span><h2 id="patient-history-heading">Other bookings</h2></div><span>Most recent first · Up to 6 shown</span></div>
      <VisitList appointments={data.appointments} />
    </section>
  </div>;
}
