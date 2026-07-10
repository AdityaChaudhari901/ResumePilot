import type { ReactNode } from "react";

import { ProductMark } from "@/components/product-mark";
import { Spotlight } from "@/components/ui/spotlight";
import { ThemeToggle } from "@/components/ui/theme-toggle";

interface StatusPageProps {
  actions: ReactNode;
  description: string;
  eyebrow: string;
  icon: ReactNode;
  title: string;
}

export function StatusPage({ actions, description, eyebrow, icon, title }: StatusPageProps) {
  return (
    <main className="relative min-h-dvh overflow-hidden bg-background">
      <Spotlight />
      <div className="relative mx-auto flex min-h-dvh max-w-7xl flex-col px-4 sm:px-6 lg:px-8">
        <header className="flex h-20 items-center justify-between border-b border-border">
          <ProductMark />
          <ThemeToggle />
        </header>
        <div className="grid flex-1 place-items-center py-12">
          <section className="w-full max-w-2xl border-l-2 border-primary pl-6 sm:pl-10">
            <div className="grid h-12 w-12 place-items-center rounded-xl border border-border-strong bg-surface-raised text-foreground shadow-sm">
              {icon}
            </div>
            <p className="mt-8 font-mono text-xs font-semibold uppercase tracking-[0.18em] text-accent">
              {eyebrow}
            </p>
            <h1 className="mt-4 text-4xl font-extrabold leading-[1.03] tracking-[-0.055em] text-foreground sm:text-6xl">
              {title}
            </h1>
            <p className="mt-5 max-w-xl text-base leading-7 text-muted-foreground">
              {description}
            </p>
            <div className="mt-8 flex flex-col gap-3 sm:flex-row">{actions}</div>
          </section>
        </div>
      </div>
    </main>
  );
}
