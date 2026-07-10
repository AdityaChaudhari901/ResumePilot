import {
  ArrowRight,
  BadgeCheck,
  FileCheck2,
  Fingerprint,
  LogIn,
  ScanSearch,
  ShieldCheck
} from "lucide-react";

import { ProductMark } from "@/components/product-mark";
import { Badge } from "@/components/ui/badge";
import { BentoGrid, BentoGridItem } from "@/components/ui/bento-grid";
import { BlurFade } from "@/components/ui/blur-fade";
import { ButtonLink } from "@/components/ui/button-link";
import { Spotlight } from "@/components/ui/spotlight";
import { ThemeToggle } from "@/components/ui/theme-toggle";
import type { DashboardAuthSession } from "@/features/dashboard/types";

interface AuthRequiredPanelProps {
  session: Extract<DashboardAuthSession, { isAuthenticated: false }>;
}

export function AuthRequiredPanel({ session }: AuthRequiredPanelProps) {
  const canAuthenticate = session.provider === "clerk" && session.canSignIn;
  const accessMessage = canAuthenticate
    ? "Sign in to open your tenant-scoped workspace."
    : "Authentication is temporarily unavailable. No private workspace data was loaded.";

  return (
    <main className="relative min-h-dvh overflow-hidden bg-background">
      <Spotlight />
      <div className="relative mx-auto flex min-h-dvh max-w-[90rem] flex-col px-4 sm:px-6 lg:px-8">
        <header className="flex h-20 items-center justify-between border-b border-border">
          <ProductMark />
          <div className="flex items-center gap-2">
            <Badge className="hidden sm:inline-flex" tone="neutral">
              private by default
            </Badge>
            <ThemeToggle />
            {canAuthenticate ? (
              <ButtonLink
                className="h-9"
                href="/sign-in"
                icon={<LogIn className="h-4 w-4" aria-hidden="true" />}
                variant="secondary"
              >
                Sign in
              </ButtonLink>
            ) : null}
          </div>
        </header>

        <section className="grid flex-1 items-center gap-12 py-12 lg:grid-cols-[minmax(0,1.08fr)_minmax(30rem,0.92fr)] lg:py-20">
          <BlurFade>
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="primary">Evidence before polish</Badge>
              <span className="font-mono text-[0.68rem] uppercase tracking-[0.15em] text-muted-foreground">
                source / prove / approve
              </span>
            </div>
            <h1 className="mt-7 max-w-4xl text-5xl font-extrabold leading-[0.98] tracking-[-0.065em] text-foreground sm:text-6xl lg:text-7xl">
              Make the application stronger. Keep every claim true.
            </h1>
            <p className="mt-7 max-w-2xl text-base leading-8 text-muted-foreground sm:text-lg">
              ResumePilot turns a job description and your existing resume into a traceable
              application workspace. Review the evidence, challenge the gaps, and approve only the
              changes you can stand behind.
            </p>

            <div className="mt-8 flex flex-col gap-3 sm:flex-row">
              {canAuthenticate ? (
                <>
                  <ButtonLink
                    className="h-11 px-5"
                    href="/sign-in"
                    icon={<ArrowRight className="h-4 w-4" aria-hidden="true" />}
                  >
                    Open my workspace
                  </ButtonLink>
                  <ButtonLink className="h-11 px-5" href="/sign-up" variant="secondary">
                    Create an account
                  </ButtonLink>
                </>
              ) : null}
            </div>

            <div className="mt-8 flex max-w-2xl items-start gap-3 border-l-2 border-primary pl-4 text-sm leading-6 text-muted-foreground">
              <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-validation" aria-hidden="true" />
              <div>
                <p className="font-bold text-foreground">Tenant isolation is active.</p>
                <p>{accessMessage}</p>
              </div>
            </div>
          </BlurFade>

          <BlurFade className="relative" delay={0.08}>
            <div className="rp-dot-field absolute -inset-6 -z-10 rounded-[2rem] opacity-45" aria-hidden="true" />
            <BentoGrid aria-label="ResumePilot evidence workflow">
              <BentoGridItem
                className="sm:col-span-2"
                eyebrow="01 / Source"
                icon={<ScanSearch className="h-4 w-4" aria-hidden="true" />}
                title="Inspect what the job posting actually says"
              >
                URL and pasted-text intake lead to a reviewable role profile before analysis starts.
                Missing or blocked source text stops the workflow instead of being guessed.
              </BentoGridItem>
              <BentoGridItem
                eyebrow="02 / Prove"
                icon={<Fingerprint className="h-4 w-4" aria-hidden="true" />}
                title="Trace suggestions to resume evidence"
              >
                Matching, gaps, and tailored bullets retain the evidence IDs that support them.
              </BentoGridItem>
              <BentoGridItem
                eyebrow="03 / Approve"
                icon={<FileCheck2 className="h-4 w-4" aria-hidden="true" />}
                title="Keep export behind a human decision"
              >
                Live AI drafts and tailored resume changes stay reviewable before files are unlocked.
              </BentoGridItem>
              <article className="flex items-center justify-between gap-4 rounded-2xl border border-foreground bg-foreground p-5 text-background sm:col-span-2">
                <div>
                  <p className="font-mono text-[0.68rem] uppercase tracking-[0.15em] text-background/60">
                    Product boundary
                  </p>
                  <p className="mt-2 max-w-md text-sm font-bold leading-6">
                    AI proposes. Validation checks. You decide.
                  </p>
                </div>
                <BadgeCheck className="h-7 w-7 shrink-0 text-primary" aria-hidden="true" />
              </article>
            </BentoGrid>
          </BlurFade>
        </section>

        <footer className="flex flex-col gap-2 border-t border-border py-6 text-xs text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
          <p>ResumePilot, an evidence-first job application workspace.</p>
          <p className="font-mono">No unsupported claims / no silent export</p>
        </footer>
      </div>
    </main>
  );
}
