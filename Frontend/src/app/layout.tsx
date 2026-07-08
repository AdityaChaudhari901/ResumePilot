import type { Metadata } from "next";

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
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
