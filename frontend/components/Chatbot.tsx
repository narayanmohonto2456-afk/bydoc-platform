"use client";

import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import Link from "next/link";
import { useAuth } from "@/components/AuthProvider";
import { ApiError, apiRequest, postJson } from "@/lib/api";

type ChatMessage = { role: "user" | "assistant"; content: string; topic?: string };
type SupportCase = { id: string; reference: string; subject: string; status: string };

const categories = [
  ["appointment", "Appointment or scheduling"], ["clinic", "Clinic experience"],
  ["doctor_directory", "Doctor directory"], ["account_access", "Account access"],
  ["notification", "Notification or reminder"], ["fee_or_payment", "Fee or payment"],
  ["accessibility", "Accessibility"], ["privacy", "Privacy concern"], ["other", "Other app issue"],
] as const;

function actionFor(topic?: string) {
  switch (topic) {
    case "BOOKING": return { href: "/appointments", label: "Find an appointment" };
    case "PASSWORD": return { href: "/forgot-password", label: "Reset password" };
    case "LOGIN": return { href: "/login", label: "Sign in" };
    case "REGISTRATION": return { href: "/register", label: "Create account" };
    case "PROFILE":
    case "VERIFICATION": return { href: "/account", label: "My account" };
    default: return null;
  }
}

const suggestions = [
  "How do I create an account?",
  "How can I reset my password?",
  "How do I book an appointment?",
  "Where can I find support?",
];

export function Chatbot() {
  const { user, loading } = useAuth();
  const [open, setOpen] = useState(false);
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [aiEnabled, setAiEnabled] = useState(false);
  const [view, setView] = useState<"chat" | "support" | "requests">("chat");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [category, setCategory] = useState("appointment");
  const [subject, setSubject] = useState("");
  const [description, setDescription] = useState("");
  const [createdReference, setCreatedReference] = useState("");
  const [cases, setCases] = useState<SupportCase[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);
  const bodyRef = useRef<HTMLDivElement>(null);
  const currentUserId = useRef(user?.id);
  currentUserId.current = user?.id;

  useEffect(() => {
    setMessages([]);
    setDraft("");
    setError("");
    setBusy(false);
    setCases([]);
    setCreatedReference("");
    setSubject("");
    setDescription("");
    setView("chat");
  }, [user?.id]);

  useEffect(() => {
    if (!open) return;
    inputRef.current?.focus();
    if (enabled !== null) return;
    apiRequest<{ enabled: boolean; ai_enabled: boolean }>("/assistant/status/")
      .then((result) => { setEnabled(result.enabled); setAiEnabled(result.ai_enabled); })
      .catch(() => setEnabled(false));
  }, [open, enabled]);

  useEffect(() => {
    if (bodyRef.current) bodyRef.current.scrollTop = bodyRef.current.scrollHeight;
  }, [messages, busy]);

  async function send(value: string) {
    const message = value.trim();
    if (!message || busy || !user || !enabled) return;
    const previousMessages = messages;
    const history = messages.slice(-6).map(({ role, content }) => ({ role, content }));
    const userId = user.id;
    setBusy(true);
    setError("");
    setDraft("");
    setMessages((current) => [...current, { role: "user", content: message }]);
    try {
      const result = await postJson<{ reply: string; topic: string }>("/assistant/chat/", { message, history });
      if (currentUserId.current === userId) {
        setMessages((current) => [...current, { role: "assistant", content: result.reply, topic: result.topic }]);
      }
    } catch (cause) {
      if (currentUserId.current === userId) {
        setMessages(previousMessages);
        setDraft(message);
        setError(cause instanceof ApiError && cause.status === 429
          ? "You have reached the chat limit. Please try again in a few minutes."
          : "The guide could not reply. You can still contact support below.");
      }
    } finally {
      if (currentUserId.current === userId) {
        setBusy(false);
        inputRef.current?.focus();
      }
    }
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void send(draft);
  }

  async function showRequests() {
    if (!user) return;
    const userId = user.id;
    setView("requests");
    setError("");
    setBusy(true);
    try {
      const result = await apiRequest<SupportCase[]>("/support/cases/?mine=1");
      if (currentUserId.current === userId) setCases(result);
    } catch (cause) {
      if (currentUserId.current === userId) setError(cause instanceof ApiError ? cause.message : "Could not load requests.");
    } finally {
      if (currentUserId.current === userId) setBusy(false);
    }
  }

  async function createRequest(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!user || busy || !subject.trim() || !description.trim()) return;
    const userId = user.id;
    setBusy(true);
    setError("");
    try {
      const result = await postJson<SupportCase>("/support/cases/", {
        category, subject: subject.trim(), description: description.trim(),
      });
      if (currentUserId.current === userId) {
        setCreatedReference(result.reference);
        setSubject("");
        setDescription("");
      }
    } catch (cause) {
      if (currentUserId.current === userId) setError(cause instanceof ApiError ? cause.message : "Could not send request. Please try again.");
    } finally {
      if (currentUserId.current === userId) setBusy(false);
    }
  }

  return <div className="chatbot-root">
    {open && <section id="chatbot-panel" className="chatbot-panel" role="dialog" aria-label="BYdoc help">
      <div className="chatbot-heading">
        <div className="chatbot-avatar" aria-hidden="true">✳</div>
        <div><strong>BYdoc help</strong><small>Guidance and support requests</small></div>
        <button type="button" className="chatbot-close" aria-label="Close assistant" onClick={() => setOpen(false)}>×</button>
      </div>
      {view !== "chat" && <button className="chatbot-back" type="button" onClick={() => { setView("chat"); setError(""); setCreatedReference(""); }}>← Back to guide</button>}
      {view === "chat" && <>
        <div className="chatbot-body" ref={bodyRef} aria-live="polite" aria-relevant="additions text">
          <p className="chatbot-intro">Hi! I can help you book, use your account, or contact support.</p>
          <p className="chatbot-privacy">I cannot give medical advice or emergency help. Do not share passwords, codes, or health details.</p>
          {!loading && !user && <div className="chatbot-links">Sign in to chat or send a request. <Link href="/login" onClick={() => setOpen(false)}>Sign in</Link> · <Link href="/register" onClick={() => setOpen(false)}>Create account</Link></div>}
          {user && enabled === false && <p className="chatbot-offline">The guide is temporarily unavailable. You can still contact support below.</p>}
          {messages.map((entry, index) => <div key={index} className={`chatbot-message chatbot-message-${entry.role}`}>
            <span>{entry.content}</span>
            {entry.role === "assistant" && actionFor(entry.topic) && <Link className="chatbot-action" href={actionFor(entry.topic)!.href} onClick={() => setOpen(false)}>{actionFor(entry.topic)!.label} →</Link>}
            {entry.role === "assistant" && entry.topic === "SUPPORT" && <button className="chatbot-action" type="button" onClick={() => setView("support")}>Contact support →</button>}
          </div>)}
          {busy && <p className="chatbot-thinking" role="status">Finding an answer…</p>}
        </div>
        {messages.length === 0 && user && enabled && <div className="chatbot-suggestions" aria-label="Suggested questions">
          {suggestions.map((suggestion) => <button key={suggestion} type="button" onClick={() => void send(suggestion)}>{suggestion}</button>)}
        </div>}
        <div className="chatbot-quicklinks"><Link href="/appointments" onClick={() => setOpen(false)}>Find care</Link><button type="button" onClick={() => { setView("support"); setError(""); }}>Contact support</button><button type="button" onClick={() => void showRequests()} disabled={!user}>My requests</button></div>
        <form className="chatbot-form" onSubmit={submit}>
          <label className="sr-only" htmlFor="chatbot-input">Ask the BYdoc guide</label>
          <input id="chatbot-input" ref={inputRef} value={draft} onChange={(event) => setDraft(event.target.value)} maxLength={600} placeholder={!user ? "Sign in to chat" : enabled ? "Ask about BYdoc…" : "Guide unavailable"} disabled={!user || !enabled || busy} />
          <button type="submit" aria-label="Send message" disabled={!draft.trim() || !user || !enabled || busy}>➤</button>
        </form>
      </>}
      {view === "support" && <div className="chatbot-workflow">
        {createdReference ? <div className="chatbot-success" role="status"><strong>Request sent</strong><p>Your reference is <b>{createdReference}</b>. Keep it for follow-up. This is not live chat.</p><button type="button" onClick={() => void showRequests()}>View my requests</button></div> : <>
          <h3>Contact support</h3><p>Tell us about an account, booking, or app issue. A team member can follow up through your request.</p>
          {!user ? <p><Link href="/login" onClick={() => setOpen(false)}>Sign in</Link> to send a request.</p> : <form className="chatbot-support-form" onSubmit={(event) => void createRequest(event)}>
            <label>Topic<select value={category} onChange={(event) => setCategory(event.target.value)}>{categories.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
            <label>Short summary<input value={subject} onChange={(event) => setSubject(event.target.value)} maxLength={160} required placeholder="What went wrong?" /></label>
            <label>Details<textarea value={description} onChange={(event) => setDescription(event.target.value)} maxLength={3000} rows={4} required placeholder="Include a booking reference or steps you tried, if relevant." /></label>
            <p className="chatbot-privacy">Only this form is sent to support. Chat messages are not attached. Do not include health records, passwords, or verification codes.</p>
            <button type="submit" disabled={busy || !subject.trim() || !description.trim()}>{busy ? "Sending…" : "Send support request"}</button>
          </form>}
        </>}
      </div>}
      {view === "requests" && <div className="chatbot-workflow">
        <h3>My requests</h3><p>Recent support cases on this account.</p>
        {busy && <p role="status">Loading requests…</p>}
        {!busy && !error && (cases.length ? <ul className="chatbot-case-list">{cases.slice(0, 10).map((item) => <li key={item.id}><strong>{item.subject}</strong><span>{item.reference} · {item.status.replaceAll("_", " ")}</span></li>)}</ul> : <p>No requests yet.</p>)}
        <button type="button" className="chatbot-new-request" onClick={() => { setView("support"); setCreatedReference(""); setError(""); }}>New request</button>
      </div>}
      {error && <p className="chatbot-error" role="alert">{error}</p>}
      {view === "chat" && user && <p className="chatbot-mode">{aiEnabled ? "AI topic routing on" : "Guided help available"}</p>}
    </section>}
    <button type="button" className="chatbot-toggle" aria-controls="chatbot-panel" aria-expanded={open} onClick={() => setOpen((value) => !value)}>
      <span aria-hidden="true">{open ? "×" : "✳"}</span><span>{open ? "Close help" : "Ask BYdoc"}</span>
    </button>
  </div>;
}
