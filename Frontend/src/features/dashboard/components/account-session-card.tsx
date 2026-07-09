import { LogIn, ShieldCheck, UserCircle } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { ButtonLink } from "@/components/ui/button-link";
import { Panel } from "@/components/ui/panel";
import type { DashboardAuthSession } from "@/features/dashboard/types";

interface AccountSessionCardProps {
  session: DashboardAuthSession | null;
}

export function AccountSessionCard({ session }: AccountSessionCardProps) {
  return (
    <Panel as="aside" eyebrow="Account" title="Session">
      {session?.isAuthenticated ? (
        <div className="space-y-4">
          <div className="rounded-md border border-border bg-surface p-3">
            <div className="flex items-center gap-2 text-sm font-semibold">
              <UserCircle className="h-4 w-4 text-primary" aria-hidden="true" />
              {session.displayName ?? session.email ?? "Authenticated user"}
            </div>
            <p className="mt-2 break-all font-mono text-xs text-muted-foreground">
              {session.email ?? session.externalId}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="success">authenticated</Badge>
            <Badge tone="primary">{session.provider}</Badge>
            <Badge tone="neutral">tenant scoped</Badge>
          </div>
          <p className="flex items-start gap-2 text-xs leading-5 text-muted-foreground">
            <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-validation" aria-hidden="true" />
            Protected dashboard session.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          <p className="text-sm leading-6 text-muted-foreground">
            {session?.reason ?? "Sign in to continue."}
          </p>
          {session?.provider === "clerk" && session.canSignIn ? (
            <ButtonLink
              className="w-full"
              href="/sign-in"
              icon={<LogIn className="h-4 w-4" aria-hidden="true" />}
              variant="primary"
            >
              Sign in
            </ButtonLink>
          ) : null}
        </div>
      )}
    </Panel>
  );
}
