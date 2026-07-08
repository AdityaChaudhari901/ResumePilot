import { Activity, Server, WifiOff } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import type { HealthStatus } from "@/features/dashboard/types";
import { cn } from "@/lib/cn";

interface HealthStripProps {
  health: HealthStatus | null;
  isLoading: boolean;
}

export function HealthStrip({ health, isLoading }: HealthStripProps) {
  const isHealthy = health?.status === "ok";
  const Icon = isHealthy ? Activity : WifiOff;

  return (
    <div className="grid gap-3 md:grid-cols-3">
      <div className="rounded-lg border border-border bg-surface p-3">
        <div className="flex items-center gap-2 text-sm font-semibold">
          <Server className="h-4 w-4 text-primary" aria-hidden="true" />
          FastAPI
        </div>
        <p className="mt-2 truncate text-xs text-muted-foreground">
          {health?.backendBaseUrl ?? "Checking backend"}
        </p>
      </div>
      <div className="rounded-lg border border-border bg-surface p-3">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-sm font-semibold">
            <Icon
              className={cn("h-4 w-4", isHealthy ? "text-validation" : "text-warning")}
              aria-hidden="true"
            />
            Status
          </div>
          <Badge tone={isHealthy ? "success" : "warning"}>
            {isLoading ? "checking" : (health?.status ?? "unknown")}
          </Badge>
        </div>
        <p className="mt-2 text-xs text-muted-foreground">
          {health?.message ?? `${health?.latencyMs ?? 0}ms round trip`}
        </p>
      </div>
      <div className="rounded-lg border border-border bg-surface p-3">
        <p className="text-sm font-semibold">Runtime</p>
        <p className="mt-2 text-xs text-muted-foreground">
          {health?.backend?.environment ?? "development"} · {health?.backend?.app ?? "ResumePilot"}
        </p>
      </div>
    </div>
  );
}
