import {
  BriefcaseBusiness,
  CheckCircle2,
  ExternalLink,
  FileCheck2,
  Send
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Panel } from "@/components/ui/panel";
import type {
  ApplicationItem,
  ApplicationStatus
} from "@/features/dashboard/types";
import { scoreMetricLabel } from "@/features/dashboard/utils/report";

interface ApplicationPipelineCardProps {
  activeApplicationId: number | null;
  applications: ApplicationItem[];
  isBusy: boolean;
  isLoading: boolean;
  onSelectApplication: (application: ApplicationItem) => void;
  onUpdateStatus: (application: ApplicationItem, status: ApplicationStatus) => void;
}

export function ApplicationPipelineCard({
  activeApplicationId,
  applications,
  isBusy,
  isLoading,
  onSelectApplication,
  onUpdateStatus
}: ApplicationPipelineCardProps) {
  return (
    <Panel as="aside" eyebrow="Workspace" title="Application pipeline">
      <div className="space-y-3">
        {isLoading ? (
          <div className="rounded-md border border-border bg-surface p-3 text-sm text-muted-foreground">
            Loading applications...
          </div>
        ) : null}

        {!isLoading && applications.length === 0 ? (
          <div className="rounded-md border border-border bg-surface p-3 text-sm leading-6 text-muted-foreground">
            No saved applications yet. Review a job description to create one.
          </div>
        ) : null}

        {applications.map((application) => (
          <ApplicationPipelineRow
            application={application}
            isActive={application.id === activeApplicationId}
            isBusy={isBusy}
            key={application.id}
            onSelect={() => onSelectApplication(application)}
            onUpdateStatus={(status) => onUpdateStatus(application, status)}
          />
        ))}
      </div>
    </Panel>
  );
}

interface ApplicationPipelineRowProps {
  application: ApplicationItem;
  isActive: boolean;
  isBusy: boolean;
  onSelect: () => void;
  onUpdateStatus: (status: ApplicationStatus) => void;
}

function ApplicationPipelineRow({
  application,
  isActive,
  isBusy,
  onSelect,
  onUpdateStatus
}: ApplicationPipelineRowProps) {
  const title = application.role ?? "Untitled role";
  const company = application.company ?? "Unknown company";
  const hasReport = application.report_id !== null;

  return (
    <article
      className="rounded-md border border-border bg-surface p-3"
      aria-current={isActive ? "true" : undefined}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex min-w-0 items-center gap-2">
            <BriefcaseBusiness className="h-4 w-4 shrink-0 text-primary" aria-hidden="true" />
            <h3 className="truncate text-sm font-semibold text-foreground">{title}</h3>
          </div>
          <p className="mt-1 truncate text-xs text-muted-foreground">{company}</p>
        </div>
        <Badge tone={statusTone(application.status)}>{statusLabel(application.status)}</Badge>
      </div>

      <dl className="mt-3 grid grid-cols-2 gap-2 text-xs">
        <div>
          <dt className="text-muted-foreground">
            {application.scoring_version === "evidence_v2" ? "Evidence fit" : "Historical score"}
          </dt>
          <dd className="mt-1 font-semibold text-foreground">
            {application.match_score === null ? "Pending" : `${Math.round(application.match_score)}%`}
          </dd>
          {application.match_score === null ? null : (
            <dd className="mt-1 text-[0.7rem] font-normal text-muted-foreground">
              {scoreMetricLabel(application.scoring_version, application.score_status)}
            </dd>
          )}
        </div>
        <div>
          <dt className="text-muted-foreground">Updated</dt>
          <dd className="mt-1 font-semibold text-foreground">
            {formatShortDate(application.updated_at)}
          </dd>
        </div>
      </dl>

      <div className="mt-3 flex flex-wrap justify-end gap-2">
        <Button
          className="h-8 px-3 text-xs"
          disabled={isBusy}
          icon={<ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />}
          onClick={onSelect}
          variant="secondary"
        >
          Open
        </Button>
        <Button
          className="h-8 px-3 text-xs"
          disabled={
            isBusy ||
            !hasReport ||
            application.status === "exported" ||
            application.status === "applied"
          }
          icon={<FileCheck2 className="h-3.5 w-3.5" aria-hidden="true" />}
          onClick={() => onUpdateStatus("exported")}
          variant="secondary"
        >
          Exported
        </Button>
        <Button
          className="h-8 px-3 text-xs"
          disabled={isBusy || !hasReport || application.status === "applied"}
          icon={<Send className="h-3.5 w-3.5" aria-hidden="true" />}
          onClick={() => onUpdateStatus("applied")}
          variant="secondary"
        >
          Applied
        </Button>
      </div>

      {isActive ? (
        <div className="mt-3 flex items-center gap-2 border-t border-border pt-3 text-xs text-muted-foreground">
          <CheckCircle2 className="h-3.5 w-3.5 text-validation" aria-hidden="true" />
          Active workspace item
        </div>
      ) : null}
    </article>
  );
}

function statusTone(status: ApplicationStatus) {
  if (status === "applied") {
    return "success";
  }
  if (status === "exported" || status === "analyzed") {
    return "primary";
  }
  if (status === "reviewed") {
    return "warning";
  }
  return "neutral";
}

function statusLabel(status: ApplicationStatus): string {
  const labels: Record<ApplicationStatus, string> = {
    analyzed: "Report ready",
    applied: "Applied",
    draft: "Draft",
    exported: "Exported",
    reviewed: "Reviewed"
  };
  return labels[status];
}

function formatShortDate(value: string): string {
  return new Intl.DateTimeFormat("en", {
    day: "numeric",
    month: "short"
  }).format(new Date(value));
}
