import type { Metadata } from "next";
import { AuthProvider } from "@/components/AuthProvider";
import { Nav } from "@/components/Nav";
import "./globals.css";

export const metadata: Metadata = {
  title: "SehatSaathi",
  description: "Find care and manage your outpatient appointments.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" data-scroll-behavior="smooth">
      <body>
        <AuthProvider>
          <a className="skip-link" href="#main-content">Skip to main content</a>
          <Nav />
          <main id="main-content">{children}</main>
          <footer className="site-footer"><div className="shell footer-row"><span className="footer-brand">SehatSaathi <span aria-hidden="true">✳</span></span><span>Thoughtful care starts here.</span><span>© {new Date().getFullYear()} SehatSaathi</span></div></footer>
        </AuthProvider>
      </body>
    </html>
  );
}
