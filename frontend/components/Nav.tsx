"use client";

import Link from "next/link";
import { useAuth } from "@/components/AuthProvider";

export function Nav() {
  const { user, loading } = useAuth();
  return (
    <header className="site-header">
      <div className="shell header-row">
        <Link href="/" className="brand" aria-label="SehatSaathi home">
          <span className="brand-mark" aria-hidden="true">+</span>
          SehatSaathi
        </Link>
        <nav aria-label="Main navigation" className="nav-links">
          <Link href="/">Home</Link>
          {!loading && (user ? <Link href="/account">My account</Link> : <Link href="/login">Sign in</Link>)}
        </nav>
      </div>
    </header>
  );
}
