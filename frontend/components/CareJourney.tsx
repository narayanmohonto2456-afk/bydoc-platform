"use client";

import { useState } from "react";
import Link from "next/link";

const steps = [
  {
    number: "01",
    title: "Create your space",
    description: "Start with a patient account that keeps your details in one place.",
    detail: "A few details today make every future visit easier to prepare for.",
    action: "Create an account",
    href: "/register",
    icon: "✦",
  },
  {
    number: "02",
    title: "Keep details current",
    description: "Add your contact and emergency details when you need them.",
    detail: "You control your profile, and you can update it any time.",
    action: "Go to my profile",
    href: "/account",
    icon: "◌",
  },
  {
    number: "03",
    title: "Stay connected",
    description: "Verify a recovery email so you can regain access securely.",
    detail: "A verified email helps you reset your password if you forget it.",
    action: "Set up recovery",
    href: "/account",
    icon: "↗",
  },
] as const;

export function CareJourney() {
  const [active, setActive] = useState(0);
  const step = steps[active];

  function onKeyDown(event: React.KeyboardEvent<HTMLButtonElement>, index: number) {
    const next = event.key === "ArrowRight" ? index + 1 : event.key === "ArrowLeft" ? index - 1 : null;
    if (next === null) return;
    event.preventDefault();
    const target = (next + steps.length) % steps.length;
    setActive(target);
    document.getElementById(`journey-tab-${target}`)?.focus();
  }

  return (
    <section className="journey section-wrap" aria-labelledby="journey-heading">
      <div className="section-heading">
        <div><span className="eyebrow">A better start</span><h2 id="journey-heading">Your care journey, one step at a time.</h2></div>
        <p>Explore what you can do with your SehatSaathi account today.</p>
      </div>
      <div className="journey-layout">
        <div className="journey-tabs" role="tablist" aria-label="Account setup steps">
          {steps.map((item, index) => (
            <button
              key={item.number}
              id={`journey-tab-${index}`}
              className={`journey-tab${active === index ? " is-active" : ""}`}
              type="button"
              role="tab"
              aria-selected={active === index}
              aria-controls="journey-panel"
              tabIndex={active === index ? 0 : -1}
              onClick={() => setActive(index)}
              onKeyDown={event => onKeyDown(event, index)}
            >
              <span className="journey-number">{item.number}</span>
              <span><strong>{item.title}</strong><small>{item.description}</small></span>
              <span aria-hidden="true" className="journey-arrow">↗</span>
            </button>
          ))}
        </div>
        <div id="journey-panel" className="journey-panel" role="tabpanel" aria-labelledby={`journey-tab-${active}`} tabIndex={0}>
          <div key={active} className="journey-panel-content">
            <span className="journey-panel-icon" aria-hidden="true">{step.icon}</span>
            <span className="eyebrow">Step {step.number}</span>
            <h3>{step.title}</h3>
            <p>{step.detail}</p>
            <Link href={step.href} className="text-link">{step.action}<span aria-hidden="true"> ↗</span></Link>
          </div>
        </div>
      </div>
    </section>
  );
}
