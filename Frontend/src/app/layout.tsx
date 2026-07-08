import type { Metadata } from "next";
import { ClerkProvider } from "@clerk/nextjs";

import "./globals.css";

export const metadata: Metadata = {
  title: "ResumePilot",
  description: "Evidence-backed resume and job-fit dashboard"
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  const document = (
    <html lang="en">
      <body>{children}</body>
    </html>
  );

  if (process.env.RESUMEPILOT_AUTH_PROVIDER === "clerk") {
    return <ClerkProvider>{document}</ClerkProvider>;
  }

  return document;
}
