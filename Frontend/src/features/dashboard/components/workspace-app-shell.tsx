"use client";

import {
  BriefcaseBusiness,
  FileText,
  LayoutDashboard,
  Plus,
  RefreshCcw,
  Settings2
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { ProductMark } from "@/components/product-mark";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ThemeToggle } from "@/components/ui/theme-toggle";
import type { DashboardAuthSession } from "@/features/dashboard/types";
import { cn } from "@/lib/cn";

interface WorkspaceAppShellProps {
  children: ReactNode;
  isRefreshing: boolean;
  onRefresh: () => void;
  session: Extract<DashboardAuthSession, { isAuthenticated: true }>;
}

const NAVIGATION = [
  {
    href: "/app/dashboard",
    icon: LayoutDashboard,
    label: "Dashboard",
    match: (pathname: string) => pathname === "/app" || pathname === "/app/dashboard"
  },
  {
    href: "/app/applications",
    icon: BriefcaseBusiness,
    label: "Applications",
    match: (pathname: string) => pathname.startsWith("/app/applications")
  },
  {
    href: "/app/reports",
    icon: FileText,
    label: "Reports",
    match: (pathname: string) => pathname.startsWith("/app/reports")
  },
  {
    href: "/app/settings",
    icon: Settings2,
    label: "Settings",
    match: (pathname: string) => pathname.startsWith("/app/settings")
  }
] as const;

export function WorkspaceAppShell({
  children,
  isRefreshing,
  onRefresh,
  session
}: WorkspaceAppShellProps) {
  const pathname = usePathname();
  const identity = session.displayName || session.email || "Private workspace";

  return (
    <div className="min-h-dvh bg-background text-foreground">
      <a
        className="fixed left-4 top-3 z-[60] -translate-y-20 rounded-lg bg-foreground px-4 py-2 text-sm font-bold text-background transition-transform focus:translate-y-0"
        href="#workspace-main"
      >
        Skip to content
      </a>

      <aside className="fixed inset-y-0 left-0 z-40 hidden w-64 border-r border-border bg-background lg:flex lg:flex-col">
        <div className="flex h-20 items-center border-b border-border px-6">
          <ProductMark href="/app/dashboard" />
        </div>

        <div className="flex flex-1 flex-col px-4 py-5">
          <Link
            className="mb-6 inline-flex min-h-11 items-center justify-center gap-2 rounded-lg border border-primary bg-primary px-4 text-sm font-bold text-primary-foreground transition hover:brightness-95 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background"
            href="/app/applications/new"
          >
            <Plus className="h-4 w-4" aria-hidden="true" />
            New application
          </Link>

          <nav aria-label="Workspace navigation" className="space-y-1">
            {NAVIGATION.map((item) => (
              <WorkspaceNavigationLink
                href={item.href}
                icon={item.icon}
                isActive={item.match(pathname)}
                key={item.href}
                label={item.label}
              />
            ))}
          </nav>

          <div className="mt-auto border-t border-border pt-5">
            <p className="truncate text-sm font-semibold text-foreground">{identity}</p>
            <p className="mt-1 font-mono text-[0.65rem] uppercase tracking-[0.12em] text-muted-foreground">
              tenant scoped
            </p>
          </div>
        </div>
      </aside>

      <div className="min-h-dvh lg:pl-64">
        <header className="rp-frosted sticky top-0 z-30 border-b border-border">
          <div className="flex h-16 items-center justify-between gap-3 px-4 sm:px-6 lg:px-8">
            <ProductMark className="lg:hidden" href="/app/dashboard" />
            <div className="hidden min-w-0 items-center gap-2 lg:flex">
              <Badge tone="neutral">private workspace</Badge>
              <span className="truncate text-sm text-muted-foreground">{identity}</span>
            </div>
            <div className="flex items-center gap-1.5">
              <Button
                aria-label="Refresh workspace status"
                className="h-9 w-9 px-0"
                disabled={isRefreshing}
                onClick={onRefresh}
                title="Refresh workspace status"
                variant="ghost"
              >
                <RefreshCcw
                  className={cn("h-4 w-4", isRefreshing && "animate-spin")}
                  aria-hidden="true"
                />
              </Button>
              <ThemeToggle />
            </div>
          </div>

          <nav
            aria-label="Mobile workspace navigation"
            className="overflow-x-auto border-t border-border px-3 lg:hidden"
          >
            <div className="flex min-w-max items-center gap-1 py-2">
              {NAVIGATION.map((item) => {
                const Icon = item.icon;
                const isActive = item.match(pathname);
                return (
                  <Link
                    aria-current={isActive ? "page" : undefined}
                    className={cn(
                      "inline-flex min-h-10 items-center gap-2 rounded-lg px-3 text-sm font-semibold text-muted-foreground transition hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary",
                      isActive && "bg-muted text-foreground"
                    )}
                    href={item.href}
                    key={item.href}
                  >
                    <Icon className="h-4 w-4" aria-hidden="true" />
                    {item.label}
                  </Link>
                );
              })}
              <Link
                className="ml-1 inline-flex min-h-10 items-center gap-2 rounded-lg bg-primary px-3 text-sm font-bold text-primary-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                href="/app/applications/new"
              >
                <Plus className="h-4 w-4" aria-hidden="true" />
                New
              </Link>
            </div>
          </nav>
        </header>

        <main className="mx-auto w-full max-w-[82rem] px-4 py-6 sm:px-6 sm:py-8 lg:px-8" id="workspace-main">
          {children}
        </main>
      </div>
    </div>
  );
}

interface WorkspaceNavigationLinkProps {
  href: string;
  icon: typeof LayoutDashboard;
  isActive: boolean;
  label: string;
}

function WorkspaceNavigationLink({
  href,
  icon: Icon,
  isActive,
  label
}: WorkspaceNavigationLinkProps) {
  return (
    <Link
      aria-current={isActive ? "page" : undefined}
      className={cn(
        "flex min-h-11 items-center gap-3 rounded-lg px-3 text-sm font-semibold text-muted-foreground transition hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary",
        isActive && "bg-muted text-foreground"
      )}
      href={href}
    >
      <Icon className={cn("h-4 w-4", isActive && "text-accent")} aria-hidden="true" />
      {label}
    </Link>
  );
}

interface WorkspacePageHeaderProps {
  action?: ReactNode;
  description: string;
  eyebrow: string;
  title: string;
}

export function WorkspacePageHeader({
  action,
  description,
  eyebrow,
  title
}: WorkspacePageHeaderProps) {
  return (
    <header className="mb-6 flex flex-col gap-5 border-b border-border pb-6 sm:flex-row sm:items-end sm:justify-between">
      <div className="max-w-3xl">
        <p className="font-mono text-[0.68rem] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
          {eyebrow}
        </p>
        <h1 className="mt-2 text-3xl font-extrabold tracking-[-0.045em] text-foreground sm:text-4xl">
          {title}
        </h1>
        <p className="mt-3 text-sm leading-6 text-muted-foreground sm:text-base">{description}</p>
      </div>
      {action ? <div className="shrink-0">{action}</div> : null}
    </header>
  );
}
