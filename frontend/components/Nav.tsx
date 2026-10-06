"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/components/AuthProvider";

export function Nav() {
  const { user, loading } = useAuth();
  const pathname = usePathname();
  const [menuOpen, setMenuOpen] = useState(false);
  const closeMenu = () => setMenuOpen(false);

  return <header className="site-header">
    <div className="shell header-row">
      <Link href="/" className="brand" aria-label="SehatSaathi home" onClick={closeMenu}>
        <span className="brand-mark" aria-hidden="true">+</span><span>Sehat<span className="brand-accent">Saathi</span></span>
      </Link>
      <button className="menu-toggle" type="button" aria-controls="primary-navigation" aria-expanded={menuOpen} aria-label={menuOpen ? "Close menu" : "Open menu"} onClick={() => setMenuOpen(open => !open)}>
        <span /><span /><span />
      </button>
      <nav id="primary-navigation" aria-label="Main navigation" className={`nav-links${menuOpen ? " nav-open" : ""}`}>
        <Link href="/" aria-current={pathname === "/" ? "page" : undefined} onClick={closeMenu}>Home</Link>
        {!loading && (user ? <Link href="/account" aria-current={pathname === "/account" ? "page" : undefined} onClick={closeMenu}>My account</Link> : <>
          <Link href="/login" aria-current={pathname === "/login" ? "page" : undefined} onClick={closeMenu}>Sign in</Link>
          <Link href="/register" className="nav-cta" aria-current={pathname === "/register" ? "page" : undefined} onClick={closeMenu}>Get started <span aria-hidden="true">↗</span></Link>
        </>)}
      </nav>
    </div>
  </header>;
}
