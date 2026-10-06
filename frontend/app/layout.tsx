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
    <html lang="en">
      <body>
        <AuthProvider>
          <Nav />
          <main id="main-content">{children}</main>
        </AuthProvider>
      </body>
    </html>
  );
}
