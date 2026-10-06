import Link from "next/link";

export default function HomePage() {
  return (
    <div className="shell">
      <section className="hero" aria-labelledby="hero-title">
        <div>
          <span className="eyebrow">Care starts with clarity</span>
          <h1 id="hero-title">A simpler way to prepare for your next visit.</h1>
          <p className="lead">Create your patient account, keep your contact details current, and manage your appointment journey in one place.</p>
          <div className="actions">
            <Link href="/register" className="button">Create an account</Link>
            <Link href="/login" className="button button-secondary">Sign in</Link>
          </div>
        </div>
        <aside className="hero-card" aria-label="What you can do today">
          <div className="card-icon" aria-hidden="true">✦</div>
          <h2>Your care, organized</h2>
          <p>Keep your profile and a verified recovery email ready for appointments.</p>
          <ul className="check-list">
            <li>Private patient profile</li>
            <li>Secure account recovery</li>
            <li>Appointment features coming together</li>
          </ul>
        </aside>
      </section>
      <section className="info-grid" aria-label="About SehatSaathi">
        <article className="info-card"><h2>Find a provider</h2><p>Clinic and doctor discovery is being connected to the patient experience.</p></article>
        <article className="info-card"><h2>Book with confidence</h2><p>Appointments use live slots and a secure booking process.</p></article>
        <article className="info-card"><h2>Get support</h2><p>Help is available for account and appointment questions.</p></article>
      </section>
      <p className="site-note">SehatSaathi does not provide emergency care or medical advice. For emergencies, contact local emergency services.</p>
    </div>
  );
}
