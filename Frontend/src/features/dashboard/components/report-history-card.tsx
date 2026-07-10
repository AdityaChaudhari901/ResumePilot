import { Clock3, FileSearch, Loader2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Panel } from "@/components/ui/panel";
import type { ReportHistoryItem } from "@/features/dashboard/types";
import {
  formatScore,
  scoreMetricLabel,
  scoreTone
} from "@/features/dashboard/utils/report";

interface ReportHistoryCardProps {
  isBusy: boolean;
  isLoading: boolean;
  items: ReportHistoryItem[];
  selectedReportId: number | null;
  onSelectReport: (item: ReportHistoryItem) => void;
}

export function ReportHistoryCard({
  isBusy,
  isLoading,
  items,
  onSelectReport,
  selectedReportId
}: ReportHistoryCardProps) {
  return (
    <Panel
      action={
        isLoading ? (
          <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" aria-hidden="true" />
        ) : null
      }
      eyebrow="Workspace"
      title="Report ledger"
    >
      {items.length === 0 ? (
        <div className="rounded-md border border-dashed border-border bg-surface p-4 text-sm text-muted-foreground">
          No saved reports yet.
        </div>
      ) : (
        <div className="space-y-2">
          {items.map((item) => {
            const isSelected = item.report_id === selectedReportId;
            const title = item.role || "Untitled role";
            const company = item.company || "Unknown company";

            return (
              <button
                aria-current={isSelected ? "true" : undefined}
                className="w-full rounded-md border border-border bg-surface p-3 text-left transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/35 aria-current:border-primary/40 aria-current:bg-primary/5"
                disabled={isBusy}
                key={item.report_id}
                onClick={() => onSelectReport(item)}
                type="button"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-foreground">{title}</p>
                    <p className="mt-1 truncate text-xs text-muted-foreground">{company}</p>
                  </div>
                  <div className="shrink-0 text-right">
                    <Badge
                      tone={
                        item.scoring_version === "evidence_v2"
                          ? scoreTone(item.match_score)
                          : "neutral"
                      }
                    >
                      {formatScore(item.match_score)}
                    </Badge>
                    <p className="mt-1 text-[0.7rem] text-muted-foreground">
                      {scoreMetricLabel(item.scoring_version, item.score_status)}
                    </p>
                  </div>
                </div>
                <div className="mt-3 grid grid-cols-3 gap-2 text-xs text-muted-foreground">
                  <ReportHistoryMetric label="Matched" value={item.matched_skills_count} />
                  <ReportHistoryMetric label="Gaps" value={item.missing_skills_count} />
                  <ReportHistoryMetric label="Weak" value={item.weak_skills_count} />
                </div>
                <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                  <span className="inline-flex items-center gap-1">
                    <FileSearch className="h-3.5 w-3.5" aria-hidden="true" />
                    Report {item.report_id}
                  </span>
                  <span className="inline-flex items-center gap-1">
                    <Clock3 className="h-3.5 w-3.5" aria-hidden="true" />
                    {formatHistoryDate(item.created_at)}
                  </span>
                </div>
              </button>
            );
          })}
        </div>
      )}
    </Panel>
  );
}

function ReportHistoryMetric({ label, value }: { label: string; value: number }) {
  return (
    <span className="rounded border border-border bg-background px-2 py-1">
      <span className="font-mono text-foreground">{value}</span> {label}
    </span>
  );
}

function formatHistoryDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "Unknown time";
  }
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit"
  }).format(date);
}
