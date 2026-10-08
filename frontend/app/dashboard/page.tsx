"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/components/AuthProvider";
import { apiRequest } from "@/lib/api";

type RolesResponse = { roles: string[]; preferred: string };

export default function DashboardHome() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (loading || !user) return;
    let active = true;
    apiRequest<RolesResponse>("/dashboard/roles/")
      .then(result => { if (active) router.replace(`/dashboard/${result.preferred}`); })
      .catch(() => { if (active) setError("Could not load your dashboard. Please try again."); });
    return () => { active = false; };
  }, [loading, user?.id, router, attempt]);

  if (loading) return <div className="wide-shell"><p role="status">Loading your dashboard…</p></div>;
  if (!user) return <div className="form-shell"><div className="panel"><h1>Sign in required</h1><p><Link href="/login">Sign in</Link> to open your dashboard.</p></div></div>;
  return <div className="wide-shell"><div className="panel dashboard-loading">
    <h1>Opening your dashboard</h1>
    {error ? <><p role="alert">{error}</p><button className="button" onClick={() => { setError(""); setAttempt(value => value + 1); }}>Try again</button></> : <p role="status">Checking your access…</p>}
  </div></div>;
}
