"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Script from "next/script";

type GoogleAccounts = {
  id: {
    initialize: (options: {
      client_id: string;
      callback: (response: { credential?: string }) => void;
      auto_select: boolean;
    }) => void;
    renderButton: (element: HTMLElement, options: Record<string, string | number>) => void;
  };
};

declare global {
  interface Window { google?: { accounts: GoogleAccounts } }
}

const clientId = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID?.trim();

export function GoogleButton({ onCredential }: { onCredential: (credential: string) => Promise<void> }) {
  const container = useRef<HTMLDivElement>(null);
  const submitting = useRef(false);
  const handler = useRef(onCredential);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => { handler.current = onCredential; }, [onCredential]);

  const renderButton = useCallback(() => {
    if (!clientId || !window.google || !container.current) return;
    container.current.replaceChildren();
    window.google.accounts.id.initialize({
      client_id: clientId,
      auto_select: false,
      callback: async response => {
        if (!response.credential || submitting.current) return;
        submitting.current = true;
        setBusy(true);
        setError("");
        try {
          await handler.current(response.credential);
        } catch (cause) {
          setError(cause instanceof Error ? cause.message : "Google sign-in failed. Please try again.");
        } finally {
          submitting.current = false;
          setBusy(false);
        }
      },
    });
    window.google.accounts.id.renderButton(container.current, {
      type: "standard", theme: "outline", size: "large",
      text: "continue_with", shape: "rectangular", width: 300,
    });
  }, []);

  useEffect(() => { renderButton(); }, [renderButton]);

  if (!clientId) return <p className="google-note">Google sign-in will be available after the site owner configures it.</p>;

  return <div className="google-signin">
    <Script src="https://accounts.google.com/gsi/client" strategy="afterInteractive" onReady={renderButton} />
    <div ref={container} className="google-button-slot" />
    {busy && <p role="status">Checking your Google account…</p>}
    {error && <div className="message message-error" role="alert">{error}</div>}
  </div>;
}
