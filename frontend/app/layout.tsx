import type { Metadata } from "next";

import { AuthProvider } from "@/lib/auth-context";

import "./globals.css";

export const metadata: Metadata = {
  title: "UPI-FIP | Payment Failure Intelligence Platform",
  description:
    "Internal payment-observability console. Synthetic data only -- not a live payment processor.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
