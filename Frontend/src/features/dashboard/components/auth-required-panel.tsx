import { LogIn, ShieldCheck } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { ButtonLink } from "@/components/ui/button-link";
import { Panel } from "@/components/ui/panel";
import type { DashboardAuthSession } from "@/features/dashboard/types";

interface AuthRequiredPanelProps {
  session: Extract<DashboardAuthSession, { isAuthenticated: false }>;
}

export function AuthRequiredPanel({ session }: AuthRequiredPanelProps) {
  return (
    <main className="flex min-h-dvh items-center justify-center px-4 py-8">
      <div className="w-full max-w-md">
        <Panel eyebrow="ResumePilot" title="Sign in required">
          <div className="space-y-4">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="primary">{session.provider}</Badge>
              <Badge tone="neutral">private workspace</Badge>
            </div>
            <p className="text-sm leading-6 text-muted-foreground">{session.reason}</p>
            {session.provider === "clerk" && session.canSignIn ? (
              <ButtonLink
                className="w-full"
                href="/sign-in"
                icon={<LogIn className="h-4 w-4" aria-hidden="true" />}
              >
                Sign in
              </ButtonLink>
            ) : null}
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <ShieldCheck className="h-4 w-4 text-validation" aria-hidden="true" />
              <span>Tenant isolation active</span>
            </div>
          </div>
        </Panel>
      </div>
    </main>
  );
}
