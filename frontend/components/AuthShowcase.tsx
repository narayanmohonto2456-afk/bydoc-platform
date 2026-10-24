import Link from "next/link";

type Props = { mode: "login" | "register" };

export function AuthShowcase({ mode }: Props) {
  const returning = mode === "login";

  return <aside className="auth-showcase" aria-label="About BYdoc">
    <div className="auth-showcase-glow" aria-hidden="true" />
    <div className="auth-showcase-content">
      <div className="auth-showcase-kicker"><span className="auth-showcase-kicker-mark" aria-hidden="true">✳</span> CARE, MADE CLEARER</div>
      <p className="auth-showcase-title">{returning ? <>Welcome back to<br /><em>your care space.</em></> : <>A better start for<br /><em>every visit.</em></>}</p>
      <p>{returning ? "Your appointments, care details, and next steps are right where you left them." : "Create your space to find verified providers and book with more confidence."}</p>

      <div className="auth-journey" aria-hidden="true">
        <div className="auth-journey-head"><span className="auth-journey-symbol">✳</span><span>YOUR CARE JOURNEY</span><span className="auth-journey-dots">•••</span></div>
        <div className="auth-journey-step"><span className="auth-step-index">01</span><span><strong>Find the right care</strong><small>Explore verified providers nearby</small></span><span className="auth-step-check">✓</span></div>
        <div className="auth-journey-step"><span className="auth-step-index">02</span><span><strong>Choose your time</strong><small>See available appointments</small></span><span className="auth-step-check">✓</span></div>
        <div className="auth-journey-step"><span className="auth-step-index">03</span><span><strong>Keep it together</strong><small>Track your visits in one place</small></span><span className="auth-step-arrow">↗</span></div>
      </div>

      <div className="auth-showcase-bottom"><span className="auth-showcase-line" aria-hidden="true" /><span>Thoughtful care starts here.</span><Link href="/appointments">Explore care <span aria-hidden="true">↗</span></Link></div>
    </div>
  </aside>;
}
