import Link from "next/link";
import { CareJourney } from "@/components/CareJourney";

export default function HomePage() {
  return <>
    <div className="hero-backdrop">
      <section className="shell hero" aria-labelledby="hero-title">
        <div className="hero-copy">
          <span className="eyebrow eyebrow-pill"><span className="eyebrow-dot" /> Care feels better with a plan</span>
          <h1 id="hero-title">A little more clarity for <em>every step</em> of care.</h1>
          <p className="lead">Make a home for your health details. Set up your account, stay connected, and feel ready for what comes next.</p>
          <div className="actions">
            <Link href="/register" className="button button-large">Get started <span aria-hidden="true">↗</span></Link>
            <Link href="/appointments" className="button button-secondary button-large">Find care</Link>
          </div>
          <p className="hero-caption"><span className="caption-check" aria-hidden="true">✓</span> Simple setup <span aria-hidden="true">·</span> Your details, your control</p>
        </div>
        <div className="hero-visual" role="img" aria-label="Illustration preview of a BYdoc patient account">
          <div className="visual-orbit orbit-one" /><div className="visual-orbit orbit-two" />
          <div className="visual-spark spark-one" aria-hidden="true">✦</div><div className="visual-spark spark-two" aria-hidden="true">✧</div>
          <div className="visual-card main-visual-card">
            <div className="visual-card-top"><span className="visual-logo">+</span><span>YOUR CARE SPACE</span><span className="visual-card-dots" aria-hidden="true">•••</span></div>
            <div className="visual-card-body"><span className="visual-avatar" aria-hidden="true">✳</span><div><small>Welcome to BYdoc</small><strong>Care, made personal.</strong></div></div>
            <div className="visual-progress"><span>Getting ready</span><strong>01 / 03</strong></div>
            <div className="visual-progress-track"><span /></div>
            <div className="visual-card-foot"><span className="mini-check" aria-hidden="true">✓</span><span>Your health journey starts here</span></div>
          </div>
          <div className="floating-note"><span className="note-icon" aria-hidden="true">♡</span><span><strong>Keep it together</strong><small>Details for your next visit</small></span></div>
        </div>
      </section>
    </div>
    <div className="shell">
      <CareJourney />
      <section className="comfort-banner" aria-labelledby="comfort-heading">
        <div className="comfort-mark" aria-hidden="true">✳</div>
        <div><span className="eyebrow">Here for the everyday moments</span><h2 id="comfort-heading">Good care begins before the appointment.</h2><p>Keep your information current and your account secure as we build the rest of your appointment experience.</p></div>
        <Link href="/register" className="button button-light">Create your account <span aria-hidden="true">↗</span></Link>
      </section>
      <p className="site-note">BYdoc does not provide emergency care or medical advice. For emergencies, contact local emergency services.</p>
    </div>
  </>;
}
