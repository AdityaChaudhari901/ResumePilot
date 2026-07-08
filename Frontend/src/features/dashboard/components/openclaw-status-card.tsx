import { ExternalLink, KeyRound, MessagesSquare, Terminal } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { ButtonLink } from "@/components/ui/button-link";
import { Panel } from "@/components/ui/panel";
import type { OpenClawStatus } from "@/features/dashboard/types";

interface OpenClawStatusCardProps {
  status: OpenClawStatus | null;
}

export function OpenClawStatusCard({ status }: OpenClawStatusCardProps) {
  const readiness = status?.readiness;
  const isReady = readiness?.status === "ready";

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
              {status?.modelReference ?? "google-vertex/gemini-3.5-flash"}
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
            <p>{status?.commands.configure ?? "./Ai services/openclaw/scripts/configure_vertex_gateway.sh"}</p>
            <p>{status?.commands.setModel ?? "openclaw models set google-vertex/<model-id>"}</p>
            <p>{status?.commands.gateway ?? "./Ai services/openclaw/scripts/start_local_gateway.sh"}</p>
            <p>{status?.commands.dashboard ?? "openclaw dashboard"}</p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Badge tone={status?.gateway.reachable ? "success" : "warning"}>
            gateway {status?.gateway.reachable ? "online" : "offline"}
          </Badge>
          <Badge tone={isReady ? "success" : "warning"}>
            control {isReady ? "ready" : "needs setup"}
          </Badge>
          <Badge tone={status?.auth.projectConfigured ? "success" : "warning"}>
            GCP project {status?.auth.projectConfigured ? "set" : "not set"}
          </Badge>
          <Badge tone={status?.auth.hasGatewayToken ? "success" : "neutral"}>
            gateway token {status?.auth.hasGatewayToken ? "present" : "local prompt"}
          </Badge>
          <Badge tone="primary">{status?.auth.location ?? "not set"}</Badge>
          <Badge tone="neutral">{status?.llmProvider ?? "vertex"}</Badge>
        </div>

        <div className="grid gap-2 text-xs text-muted-foreground sm:grid-cols-3">
          <div className="rounded-md border border-border bg-surface p-2">
            <span className="font-semibold text-foreground">Model registry</span>
            <p>{readiness?.modelRegistered ? "global ready" : "global missing"}</p>
          </div>
          <div className="rounded-md border border-border bg-surface p-2">
            <span className="font-semibold text-foreground">Agent registry</span>
            <p>{readiness?.agentModelRegistered ? "agent ready" : "gateway managed"}</p>
          </div>
          <div className="rounded-md border border-border bg-surface p-2">
            <span className="font-semibold text-foreground">Main session</span>
            <p>{readiness?.mainSessionRegistered ? "registered" : "new chat needed"}</p>
          </div>
        </div>

        <p className="text-xs text-muted-foreground">
          {readiness?.dashboardLaunch ??
            "Use Open Fresh Chat to open an authenticated local Control UI tab."}
        </p>

        <div className="grid gap-2 sm:grid-cols-2">
          <ButtonLink
            className="w-full"
            href={status?.chatUrl ?? "/api/openclaw/control?view=chat"}
            icon={<ExternalLink className="h-4 w-4" aria-hidden="true" />}
            rel="noreferrer"
            target="_blank"
            variant="secondary"
          >
            Open Fresh Chat
          </ButtonLink>
          <ButtonLink
            className="w-full"
            href={status?.dashboardUrl ?? "/api/openclaw/control?view=overview"}
            icon={<ExternalLink className="h-4 w-4" aria-hidden="true" />}
            rel="noreferrer"
            target="_blank"
            variant="ghost"
          >
            Control Overview
          </ButtonLink>
        </div>
      </div>
    </Panel>
  );
}
