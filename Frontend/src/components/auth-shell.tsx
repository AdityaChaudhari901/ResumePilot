import { ArrowLeft, CheckCircle2, Fingerprint, FileCheck2, ScanSearch } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

import { ProductMark } from "@/components/product-mark";
import { BlurFade } from "@/components/ui/blur-fade";
import { Spotlight } from "@/components/ui/spotlight";
import { ThemeToggle } from "@/components/ui/theme-toggle";

interface AuthShellProps {
  children: ReactNode;
  mode: "sign-in" | "sign-up";
}

const protocol = [
  {
    description: "Capture the source role and review what was actually extracted.",
    icon: ScanSearch,
    label: "Source"
  },
  {
    description: "Link every recommendation to evidence already in your resume.",
    icon: Fingerprint,
    label: "Prove"
  },
  {
    description: "Approve supported changes before any tailored file can leave the workspace.",
    icon: FileCheck2,
    label: "Export"
  }
] as const;

export function AuthShell({ children, mode }: AuthShellProps) {
  const isSignIn = mode === "sign-in";

  return (
    <main className="relative min-h-dvh overflow-hidden bg-background">
      <Spotlight />
      <div className="relative mx-auto flex min-h-dvh w-full max-w-7xl flex-col px-4 sm:px-6 lg:px-8">
        <header className="flex h-20 items-center justify-between border-b border-border">
          <ProductMark />
          <div className="flex items-center gap-2">
            <Link
              className="inline-flex h-9 items-center gap-2 rounded-lg px-3 text-sm font-semibold text-muted-foreground transition hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
              href="/"
            >
              <ArrowLeft className="h-4 w-4" aria-hidden="true" />
              Back home
            </Link>
            <ThemeToggle />
          </div>
        </header>

        <div className="grid flex-1 items-center gap-12 py-10 lg:grid-cols-[minmax(0,1fr)_minmax(22rem,29rem)] lg:py-16">
          <BlurFade className="max-w-2xl">
            <p className="font-mono text-xs font-semibold uppercase tracking-[0.18em] text-accent">
              Private evidence workspace
            </p>
            <h1 className="mt-5 max-w-xl text-4xl font-extrabold leading-[1.04] tracking-[-0.055em] text-foreground sm:text-5xl lg:text-6xl">
              {isSignIn
                ? "Return to applications you can defend."
                : "Build applications without inventing the story."}
            </h1>
            <p className="mt-5 max-w-xl text-base leading-7 text-muted-foreground sm:text-lg">
              ResumePilot keeps job evidence, resume proof, AI suggestions, and your final approval
              in one traceable workflow.
            </p>

            <ol className="mt-10 grid gap-px overflow-hidden rounded-2xl border border-border bg-border sm:grid-cols-3">
              {protocol.map((item, index) => {
                const Icon = item.icon;
                return (
                  <li className="bg-surface-raised p-4" key={item.label}>
                    <div className="flex items-center justify-between gap-3">
                      <span className="font-mono text-[0.68rem] text-muted-foreground">
                        0{index + 1}
                      </span>
                      <Icon className="h-4 w-4 text-accent" aria-hidden="true" />
                    </div>
                    <p className="mt-6 text-sm font-bold text-foreground">{item.label}</p>
                    <p className="mt-1 text-xs leading-5 text-muted-foreground">{item.description}</p>
                  </li>
                );
              })}
            </ol>
          </BlurFade>

          <BlurFade className="relative" delay={0.08}>
            <div className="rp-dot-field absolute -inset-5 -z-10 rounded-[2rem] opacity-45" aria-hidden="true" />
            <section
              aria-label={isSignIn ? "Sign in to ResumePilot" : "Create a ResumePilot account"}
              className="rounded-[1.6rem] border border-border-strong bg-surface-raised p-2 shadow-[0_30px_90px_-45px_rgba(10,14,8,0.75)]"
            >
              {children}
            </section>
            <p className="mt-4 flex items-center justify-center gap-2 text-center text-xs leading-5 text-muted-foreground">
              <CheckCircle2 className="h-4 w-4 text-validation" aria-hidden="true" />
              Tenant-scoped session. Your workspace is private by default.
            </p>
          </BlurFade>
        </div>
      </div>
    </main>
  );
}
