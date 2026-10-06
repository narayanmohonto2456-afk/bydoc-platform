"use client";

import { useState } from "react";

type Props = {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  autoComplete: string;
  hint?: string;
};

export function PasswordField({ id, label, value, onChange, autoComplete, hint }: Props) {
  const [visible, setVisible] = useState(false);

  return <div className="field">
    <label htmlFor={id}>{label}</label>
    <div className="input-action">
      <input id={id} type={visible ? "text" : "password"} autoComplete={autoComplete} maxLength={128} required value={value} onChange={event => onChange(event.target.value)} aria-describedby={hint ? `${id}-hint` : undefined} />
      <button type="button" className="input-action-button" aria-label={`${visible ? "Hide" : "Show"} ${label.toLowerCase()}`} aria-pressed={visible} onClick={() => setVisible(current => !current)}>{visible ? "Hide" : "Show"}</button>
    </div>
    {hint && <span className="field-hint" id={`${id}-hint`}>{hint}</span>}
  </div>;
}

export function PasswordStrength({ password }: { password: string }) {
  if (!password) return null;
  const score = [password.length >= 12, /[a-z]/.test(password) && /[A-Z]/.test(password), /\d/.test(password), /[^A-Za-z0-9]/.test(password)].filter(Boolean).length;
  const label = score <= 1 ? "Needs work" : score === 2 ? "Fair" : score === 3 ? "Good" : "Strong";
  return <div className="password-strength" aria-live="polite">
    <div className="strength-track" aria-hidden="true"><span style={{ width: `${Math.max(score, 1) * 25}%` }} data-score={score} /></div>
    <span>{label} password. Aim for 12 or more characters with a mix of characters.</span>
  </div>;
}
