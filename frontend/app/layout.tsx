import type { Metadata } from "next";
import { AuthProvider } from "@/components/AuthProvider";
import { Nav } from "@/components/Nav";
import { Chatbot } from "@/components/Chatbot";
import "leaflet/dist/leaflet.css";
import "./globals.css";

export const metadata: Metadata = {
  title: "BYdoc",
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
          <Chatbot />
          <footer className="site-footer"><div className="shell footer-row"><span className="footer-brand">BYdoc <span aria-hidden="true">✳</span></span><span>Thoughtful care starts here.</span><span>© {new Date().getFullYear()} BYdoc</span></div></footer>
        </AuthProvider>
      </body>
    </html>
  );
}
