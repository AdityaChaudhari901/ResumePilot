import type { Metadata, Viewport } from "next";
import { ClerkProvider } from "@clerk/nextjs";
import Script from "next/script";

import "@fontsource-variable/manrope";
import "@fontsource/ibm-plex-mono/400.css";
import "@fontsource/ibm-plex-mono/500.css";
import "@fontsource/ibm-plex-mono/600.css";

import { shouldUseClerkProvider } from "@/lib/auth-runtime";

import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "ResumePilot | Evidence-first job applications",
    template: "%s | ResumePilot"
  },
  description:
    "Review job evidence, compare it with your resume, and approve every tailored claim before export.",
  applicationName: "ResumePilot"
};

export const viewport: Viewport = {
  colorScheme: "light dark",
  initialScale: 1,
  themeColor: [
    { color: "#f1f2e9", media: "(prefers-color-scheme: light)" },
    { color: "#0d0f0c", media: "(prefers-color-scheme: dark)" }
  ],
  width: "device-width"
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  const document = (
    <html lang="en" suppressHydrationWarning>
      <body>
        <Script src="/theme-init.js" strategy="beforeInteractive" />
        {children}
      </body>
    </html>
  );

  if (shouldUseClerkProvider(process.env)) {
    return <ClerkProvider>{document}</ClerkProvider>;
  }

  return document;
}
