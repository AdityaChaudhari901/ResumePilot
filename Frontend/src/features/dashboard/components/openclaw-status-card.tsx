import { ExternalLink, KeyRound, MessagesSquare, Terminal } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { ButtonLink } from "@/components/ui/button-link";
import { Panel } from "@/components/ui/panel";
import type { OpenClawStatus } from "@/features/dashboard/types";

interface OpenClawStatusCardProps {
  status: OpenClawStatus | null;
}

export function OpenClawStatusCard({ status }: OpenClawStatusCardProps) {
  return (
    <Panel as="aside" eyebrow="OpenClaw" title="WebChat / dashboard">
      <div className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="rounded-md border border-border bg-surface p-3">
            <div className="flex items-center gap-2 text-sm font-semibold">
              <MessagesSquare className="h-4 w-4 text-primary" aria-hidden="true" />
              Provider
            </div>
            <p className="mt-2 font-mono text-xs text-muted-foreground">
              {status?.provider ?? "google-vertex"}
            </p>
          </div>
          <div className="rounded-md border border-border bg-surface p-3">
            <div className="flex items-center gap-2 text-sm font-semibold">
              <KeyRound className="h-4 w-4 text-validation" aria-hidden="true" />
              Vertex auth
            </div>
            <p className="mt-2 text-xs text-muted-foreground">
              {status?.auth.vertexAuth ?? "gcloud ADC"}
            </p>
          </div>
        </div>

        <div className="rounded-md border border-border bg-terminal p-3 text-white">
          <div className="mb-3 flex items-center gap-2 text-sm font-semibold">
            <Terminal className="h-4 w-4 text-validation" aria-hidden="true" />
            Local commands
          </div>
          <div className="space-y-2 font-mono text-xs text-white/80">
            <p>{status?.commands.setModel ?? "openclaw models set google-vertex/<model-id>"}</p>
            <p>{status?.commands.gateway ?? "openclaw gateway run --bind loopback"}</p>
            <p>{status?.commands.dashboard ?? "openclaw dashboard"}</p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Badge tone={status?.auth.projectConfigured ? "success" : "warning"}>
            GCP project {status?.auth.projectConfigured ? "set" : "not set"}
          </Badge>
          <Badge tone={status?.auth.hasGatewayToken ? "success" : "neutral"}>
            gateway token {status?.auth.hasGatewayToken ? "present" : "local prompt"}
          </Badge>
          <Badge tone="primary">{status?.auth.location ?? "not set"}</Badge>
        </div>

        <ButtonLink
          className="w-full"
          href={status?.dashboardUrl ?? "http://127.0.0.1:18789/"}
          icon={<ExternalLink className="h-4 w-4" aria-hidden="true" />}
          rel="noreferrer"
          target="_blank"
          variant="secondary"
        >
          Open Control UI
        </ButtonLink>
      </div>
    </Panel>
  );
}
