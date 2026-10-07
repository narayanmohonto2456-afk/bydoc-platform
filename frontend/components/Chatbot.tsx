"use client";

import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import Link from "next/link";
import { useAuth } from "@/components/AuthProvider";
import { ApiError, apiRequest } from "@/lib/api";

type ChatMessage = { role: "user" | "assistant"; content: string };

const suggestions = [
  "How do I create an account?",
  "How can I reset my password?",
  "Can I book an appointment yet?",
];

export function Chatbot() {
  const { user, loading } = useAuth();
  const [open, setOpen] = useState(false);
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const bodyRef = useRef<HTMLDivElement>(null);
  const currentUserId = useRef(user?.id);
  currentUserId.current = user?.id;

  useEffect(() => {
    setMessages([]);
    setDraft("");
    setError("");
    setBusy(false);
  }, [user?.id]);

  useEffect(() => {
    if (!open) return;
    inputRef.current?.focus();
    if (enabled !== null) return;
    apiRequest<{ enabled: boolean }>("/assistant/status/")
      .then((result) => setEnabled(result.enabled))
      .catch(() => setEnabled(false));
  }, [open, enabled]);

  useEffect(() => {
    if (bodyRef.current) bodyRef.current.scrollTop = bodyRef.current.scrollHeight;
  }, [messages, busy]);

  async function send(value: string) {
    const message = value.trim();
    if (!message || busy || !user || !enabled) return;
    const previousMessages = messages;
    const history = messages.slice(-6);
    const userId = user.id;
    setBusy(true);
    setError("");
    setDraft("");
    setMessages((current) => [...current, { role: "user", content: message }]);
    try {
      const result = await apiRequest<{ reply: string }>("/assistant/chat/", {
        method: "POST",
        body: JSON.stringify({ message, history }),
      });
      if (currentUserId.current === userId) {
        setMessages((current) => [...current, { role: "assistant", content: result.reply }]);
      }
    } catch (cause) {
      if (currentUserId.current === userId) {
        setMessages(previousMessages);
        setDraft(message);
        setError(cause instanceof ApiError && cause.status === 429
          ? "You have reached the chat limit. Please try again in a few minutes."
          : "The assistant could not reply. Please try again later.");
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

  return <div className="chatbot-root">
    {open && <section id="chatbot-panel" className="chatbot-panel" role="dialog" aria-label="SehatSaathi assistant">
      <div className="chatbot-heading">
        <div className="chatbot-avatar" aria-hidden="true">✳</div>
        <div><strong>SehatSaathi guide</strong><small>Help with your account and app</small></div>
        <button type="button" className="chatbot-close" aria-label="Close assistant" onClick={() => setOpen(false)}>×</button>
      </div>
      <div className="chatbot-body" ref={bodyRef} aria-live="polite" aria-relevant="additions text">
        <p className="chatbot-intro">Hi! I can help you find your way around SehatSaathi. I cannot give medical advice or change an appointment.</p>
        <p className="chatbot-privacy">Please do not share passwords, codes, or sensitive health details here.</p>
        {!loading && !user && <div className="chatbot-links">Sign in to use AI chat. <Link href="/login" onClick={() => setOpen(false)}>Sign in</Link> · <Link href="/register" onClick={() => setOpen(false)}>Create account</Link></div>}
        {user && enabled === false && <p className="chatbot-offline">The local AI model is not connected yet. You can still use the links below.</p>}
        {messages.map((entry, index) => <p key={index} className={`chatbot-message chatbot-message-${entry.role}`}><span>{entry.content}</span></p>)}
        {busy && <p className="chatbot-thinking" role="status">Thinking<span aria-hidden="true">…</span></p>}
      </div>
      {messages.length === 0 && user && enabled && <div className="chatbot-suggestions" aria-label="Suggested questions">
        {suggestions.map((suggestion) => <button key={suggestion} type="button" onClick={() => void send(suggestion)}>{suggestion}</button>)}
      </div>}
      <div className="chatbot-quicklinks"><Link href="/account" onClick={() => setOpen(false)}>My account</Link><Link href="/forgot-password" onClick={() => setOpen(false)}>Reset password</Link></div>
      <form className="chatbot-form" onSubmit={submit}>
        <label className="sr-only" htmlFor="chatbot-input">Ask the SehatSaathi guide</label>
        <input id="chatbot-input" ref={inputRef} value={draft} onChange={(event) => setDraft(event.target.value)} maxLength={600} placeholder={!user ? "Sign in to chat" : enabled ? "Ask about the app…" : "Chat is unavailable"} disabled={!user || !enabled || busy} />
        <button type="submit" aria-label="Send message" disabled={!draft.trim() || !user || !enabled || busy}>➤</button>
      </form>
      {error && <p className="chatbot-error" role="alert">{error}</p>}
    </section>}
    <button type="button" className="chatbot-toggle" aria-controls="chatbot-panel" aria-expanded={open} onClick={() => setOpen((value) => !value)}>
      <span aria-hidden="true">{open ? "×" : "✳"}</span><span>{open ? "Close help" : "Ask SehatSaathi"}</span>
    </button>
  </div>;
}
