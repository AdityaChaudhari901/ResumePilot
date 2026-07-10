import { Activity, Gauge, WalletCards, Zap } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Panel } from "@/components/ui/panel";
import type {
  PlanLimit,
  UsageLimitMetric,
  UsageSummaryResponse
} from "@/features/dashboard/types";

interface UsageStatusCardProps {
  usage: UsageSummaryResponse | null;
}

const metricLabels: Record<UsageLimitMetric, string> = {
  analyses: "Analysis runs",
  exports: "Exports",
  live_ai_runs: "Live AI runs"
};

export function UsageStatusCard({ usage }: UsageStatusCardProps) {
  const planLabel = usage?.plan ? usage.plan.toUpperCase() : "FREE";

  return (
    <Panel as="aside" eyebrow="Usage" title="Plan usage meter">
      <div className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="rounded-md border border-border bg-surface p-3">
            <div className="flex items-center gap-2 text-sm font-semibold">
              <WalletCards className="h-4 w-4 text-primary" aria-hidden="true" />
              Plan
            </div>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <Badge tone="primary">{planLabel}</Badge>
              <Badge tone={usage?.live_ai_enabled ? "success" : "neutral"}>
                {usage?.live_ai_enabled ? "live AI allowed" : "fallback mode"}
              </Badge>
            </div>
          </div>
          <div className="rounded-md border border-border bg-surface p-3">
            <div className="flex items-center gap-2 text-sm font-semibold">
              <Activity className="h-4 w-4 text-validation" aria-hidden="true" />
              Live LLM cost
            </div>
            <p className="mt-2 font-mono text-xl font-semibold tabular-nums">
              {formatCurrency(usage?.total_cost_estimate_usd ?? 0)}
            </p>
          </div>
        </div>

        <div className="space-y-3">
          {usage ? (
            usage.limits.map((limit) => <UsageLimitRow key={limit.metric} limit={limit} />)
          ) : (
            <div className="rounded-md border border-border bg-surface p-3 text-sm text-muted-foreground">
              Loading usage limits.
            </div>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          <Gauge className="h-4 w-4 text-primary" aria-hidden="true" />
          <span>Resets {formatResetDate(usage?.current_period_end)}</span>
          <span aria-hidden="true">/</span>
          <span>{usage?.subscription_status ?? "inactive"}</span>
        </div>
        <p className="rounded-md border border-border bg-surface p-3 text-xs leading-5 text-muted-foreground">
          These counters enforce ResumePilot plan limits in the current app database. Stripe billing
          is not connected yet.
        </p>
      </div>
    </Panel>
  );
}

function UsageLimitRow({ limit }: { limit: PlanLimit }) {
  const limitLabel = limit.limit === null ? "unlimited" : String(limit.limit);
  const progressCap = limit.limit ?? Math.max(limit.used, 1);
  const progressMax = Math.max(progressCap, 1);
  const progressValue = Math.min(limit.used, progressMax);
  const tone = limit.remaining === 0 ? "warning" : "success";

  return (
    <div className="rounded-md border border-border bg-surface p-3">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Zap className="h-4 w-4 text-accent" aria-hidden="true" />
          <p className="text-sm font-medium">{metricLabels[limit.metric]}</p>
        </div>
        <Badge tone={tone}>
          {limit.used}/{limitLabel}
        </Badge>
      </div>
      <progress
        aria-label={`${metricLabels[limit.metric]} usage`}
        className="mt-3 h-2 w-full overflow-hidden rounded-full accent-primary"
        max={progressMax}
        value={progressValue}
      />
      <p className="mt-2 text-xs text-muted-foreground">
        {limit.remaining === null ? "No monthly cap" : `${limit.remaining} remaining this month`}
      </p>
    </div>
  );
}

function formatCurrency(value: number): string {
  return new Intl.NumberFormat("en-US", {
    currency: "USD",
    maximumFractionDigits: 6,
    minimumFractionDigits: 2,
    style: "currency"
  }).format(value);
}

function formatResetDate(value: string | undefined): string {
  if (!value) {
    return "monthly";
  }
  return new Intl.DateTimeFormat("en-US", {
    day: "numeric",
    month: "short"
  }).format(new Date(value));
}
