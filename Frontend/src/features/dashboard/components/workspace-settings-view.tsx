import { ShieldCheck } from "lucide-react";

import { Panel } from "@/components/ui/panel";
import { AccountSessionCard } from "@/features/dashboard/components/account-session-card";
import { HealthStrip } from "@/features/dashboard/components/health-strip";
import { OpenClawStatusCard } from "@/features/dashboard/components/openclaw-status-card";
import { UsageStatusCard } from "@/features/dashboard/components/usage-status-card";
import type {
  DashboardAuthSession,
  HealthStatus,
  OpenClawStatus,
  UsageSummaryResponse
} from "@/features/dashboard/types";

interface WorkspaceSettingsViewProps {
  health: HealthStatus | null;
  isLoading: boolean;
  openclaw: OpenClawStatus | null;
  session: DashboardAuthSession | null;
  usage: UsageSummaryResponse | null;
}

export function WorkspaceSettingsView({
  health,
  isLoading,
  openclaw,
  session,
  usage
}: WorkspaceSettingsViewProps) {
  return (
    <div className="grid min-w-0 gap-6 xl:grid-cols-2 [&>*]:min-w-0">
      <Panel className="xl:col-span-2" eyebrow="Runtime" title="Service health">
        <HealthStrip health={health} isLoading={isLoading} />
      </Panel>
      <AccountSessionCard session={session} />
      <UsageStatusCard usage={usage} />
      <OpenClawStatusCard status={openclaw} />
      <Panel as="aside" eyebrow="Product policy" title="Evidence and export boundaries">
        <ul className="space-y-4 text-sm leading-6 text-muted-foreground">
          <li className="flex items-start gap-3">
            <ShieldCheck className="mt-1 h-4 w-4 shrink-0 text-validation" aria-hidden="true" />
            Unsupported work history, credentials, skills, and metrics are blocked before a report
            is shown.
          </li>
          <li className="flex items-start gap-3">
            <ShieldCheck className="mt-1 h-4 w-4 shrink-0 text-validation" aria-hidden="true" />
            Resume recommendations retain evidence identifiers so each proposed change can be
            audited.
          </li>
          <li className="flex items-start gap-3">
            <ShieldCheck className="mt-1 h-4 w-4 shrink-0 text-validation" aria-hidden="true" />
            Markdown belongs to the report. DOCX, LaTeX, and PDF remain locked to accepted tailored
            resume drafts.
          </li>
        </ul>
      </Panel>
    </div>
  );
}
