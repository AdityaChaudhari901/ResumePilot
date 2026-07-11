import {
  ArrowRight,
  BriefcaseBusiness,
  CircleDashed,
  Plus,
  ShieldCheck
} from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Panel } from "@/components/ui/panel";
import type {
  ApplicationItem,
  ReportHistoryItem,
  UsageSummaryResponse,
  WorkflowOperation
} from "@/features/dashboard/types";
import { formatScore, scoreTone } from "@/features/dashboard/utils/report";

interface WorkspaceOverviewProps {
  activeOperation: WorkflowOperation | null;
  applications: ApplicationItem[];
  isLoading: boolean;
  reports: ReportHistoryItem[];
  usage: UsageSummaryResponse | null;
}

export function WorkspaceOverview({
  activeOperation,
  applications,
  isLoading,
  reports,
  usage
}: WorkspaceOverviewProps) {
  const latestApplications = applications.slice(0, 4);
  const latestReports = reports.slice(0, 3);
  const exportReadyCount = applications.filter((application) =>
    ["exported", "applied"].includes(application.status)
  ).length;
  const analysisLimit = usage?.limits.find((limit) => limit.metric === "analyses");

  return (
    <div className="space-y-6">
      {activeOperation ? (
        <section
          aria-labelledby="active-operation-title"
          className="flex flex-col gap-4 rounded-xl border border-warning/35 bg-warning/10 p-5 sm:flex-row sm:items-center sm:justify-between"
        >
          <div className="flex min-w-0 items-start gap-3">
            <CircleDashed className="mt-0.5 h-5 w-5 shrink-0 text-warning" aria-hidden="true" />
            <div>
              <h2 className="font-bold text-foreground" id="active-operation-title">
                {activeOperation.status === "waiting_for_approval"
                  ? "A draft is waiting for your approval"
                  : "An analysis is still in progress"}
              </h2>
              <p className="mt-1 text-sm text-muted-foreground">
                {activeOperation.status === "waiting_for_approval"
                  ? "Review the validated proposal before ResumePilot applies any generated text."
                  : `${activeOperation.progress_percent}% complete · ${formatStage(activeOperation.stage)}`}
              </p>
            </div>
          </div>
          <Link
            className="inline-flex min-h-10 shrink-0 items-center justify-center gap-2 rounded-lg border border-warning/40 bg-surface-raised px-4 text-sm font-bold text-foreground transition hover:bg-surface focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-warning"
            href={
              activeOperation.application_id
                ? `/app/applications/${activeOperation.application_id}`
                : "/app/applications/new"
            }
          >
            Resume review
            <ArrowRight className="h-4 w-4" aria-hidden="true" />
          </Link>
        </section>
      ) : null}

      <section
        aria-label="Application portfolio summary"
        className="overflow-hidden rounded-xl border border-border bg-surface-raised"
      >
        <div className="grid divide-y divide-border sm:grid-cols-3 sm:divide-x sm:divide-y-0">
          <PortfolioMetric
            detail={isLoading ? "Loading workspace" : "Saved case files"}
            label="Applications"
            value={isLoading ? "—" : String(applications.length)}
          />
          <PortfolioMetric
            detail="Evidence-backed analyses"
            label="Reports"
            value={isLoading ? "—" : String(reports.length)}
          />
          <PortfolioMetric
            detail={
              analysisLimit?.remaining === null || analysisLimit?.remaining === undefined
                ? `${exportReadyCount} export ready`
                : `${analysisLimit.remaining} analyses remaining`
            }
            label="Ready to move"
            value={isLoading ? "—" : String(exportReadyCount)}
          />
        </div>
      </section>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.35fr)_minmax(19rem,0.65fr)]">
        <Panel
          action={
            <Link
              className="text-sm font-bold text-accent hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
              href="/app/applications"
            >
              View all
            </Link>
          }
          eyebrow="Portfolio"
          title="Recent applications"
        >
          {isLoading ? (
            <div className="rounded-lg border border-border bg-surface p-5 text-sm text-muted-foreground">
              Loading your applications…
            </div>
          ) : null}
          {!isLoading && latestApplications.length === 0 ? (
            <div className="rounded-lg border border-dashed border-border-strong bg-surface p-6">
              <BriefcaseBusiness className="h-5 w-5 text-accent" aria-hidden="true" />
              <h3 className="mt-4 font-bold text-foreground">Start with one role</h3>
              <p className="mt-2 max-w-lg text-sm leading-6 text-muted-foreground">
                Capture a job source, verify its requirements, then connect the role to resume
                evidence before analysis.
              </p>
              <Link
                className="mt-5 inline-flex min-h-10 items-center gap-2 rounded-lg bg-primary px-4 text-sm font-bold text-primary-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                href="/app/applications/new"
              >
                <Plus className="h-4 w-4" aria-hidden="true" />
                New application
              </Link>
            </div>
          ) : null}
          <div className="divide-y divide-border">
            {latestApplications.map((application) => (
              <Link
                className="group grid gap-3 py-4 first:pt-0 last:pb-0 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center"
                href={`/app/applications/${application.id}`}
                key={application.id}
              >
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <BriefcaseBusiness className="h-4 w-4 shrink-0 text-accent" aria-hidden="true" />
                    <h3 className="truncate text-sm font-bold text-foreground group-hover:underline">
                      {application.role || "Untitled role"}
                    </h3>
                  </div>
                  <p className="mt-1 truncate text-xs text-muted-foreground">
                    {application.company || "Company not captured"} · Updated {formatDate(application.updated_at)}
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <Badge tone={applicationStatusTone(application.status)}>
                    {applicationStatusLabel(application.status)}
                  </Badge>
                  <ArrowRight className="h-4 w-4 text-muted-foreground transition-transform group-hover:translate-x-0.5" aria-hidden="true" />
                </div>
              </Link>
            ))}
          </div>
        </Panel>

        <div className="space-y-6">
          <Panel eyebrow="Protocol" title="How ResumePilot moves work">
            <ol className="space-y-4">
              <ProtocolStep
                detail="Capture the exact job source before interpreting it."
                index="01"
                label="Source"
              />
              <ProtocolStep
                detail="Keep recommendations linked to resume evidence."
                index="02"
                label="Prove"
              />
              <ProtocolStep
                detail="Unlock export only after a human decision."
                index="03"
                label="Approve"
              />
            </ol>
            <div className="mt-5 flex items-start gap-2 border-t border-border pt-4 text-xs leading-5 text-muted-foreground">
              <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-validation" aria-hidden="true" />
              AI drafts remain subordinate to deterministic evidence and validation.
            </div>
          </Panel>

          <Panel
            action={
              <Link
                className="text-sm font-bold text-accent hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                href="/app/reports"
              >
                Open ledger
              </Link>
            }
            eyebrow="Evidence"
            title="Latest reports"
          >
            {latestReports.length === 0 ? (
              <p className="text-sm leading-6 text-muted-foreground">
                Reports will appear here after a validated analysis completes.
              </p>
            ) : (
              <div className="space-y-3">
                {latestReports.map((report) => (
                  <Link
                    className="flex items-center justify-between gap-3 rounded-lg border border-border bg-surface p-3 transition hover:border-border-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                    href={`/app/reports/${report.report_id}`}
                    key={report.report_id}
                  >
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold text-foreground">
                        {report.role || "Untitled role"}
                      </p>
                      <p className="mt-1 truncate text-xs text-muted-foreground">
                        {report.company || "Company not captured"}
                      </p>
                    </div>
                    <Badge tone={scoreTone(report.match_score)}>{formatScore(report.match_score)}</Badge>
                  </Link>
                ))}
              </div>
            )}
          </Panel>
        </div>
      </div>
    </div>
  );
}

function PortfolioMetric({
  detail,
  label,
  value
}: {
  detail: string;
  label: string;
  value: string;
}) {
  return (
    <div className="p-5 sm:p-6">
      <p className="font-mono text-[0.66rem] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
        {label}
      </p>
      <p className="mt-2 text-3xl font-extrabold tracking-[-0.05em] text-foreground">{value}</p>
      <p className="mt-1 text-xs text-muted-foreground">{detail}</p>
    </div>
  );
}

function ProtocolStep({ detail, index, label }: { detail: string; index: string; label: string }) {
  return (
    <li className="grid grid-cols-[2rem_minmax(0,1fr)] gap-3">
      <span className="font-mono text-xs font-semibold text-accent">{index}</span>
      <div>
        <p className="text-sm font-bold text-foreground">{label}</p>
        <p className="mt-1 text-xs leading-5 text-muted-foreground">{detail}</p>
      </div>
    </li>
  );
}

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "recently";
  }
  return new Intl.DateTimeFormat(undefined, { day: "numeric", month: "short" }).format(date);
}

function formatStage(value: string): string {
  return value.replaceAll("_", " ");
}

function applicationStatusTone(status: ApplicationItem["status"]) {
  if (status === "applied") {
    return "success";
  }
  if (status === "analyzed" || status === "exported") {
    return "primary";
  }
  if (status === "reviewed") {
    return "warning";
  }
  return "neutral";
}

function applicationStatusLabel(status: ApplicationItem["status"]): string {
  const labels: Record<ApplicationItem["status"], string> = {
    analyzed: "Report ready",
    applied: "Applied",
    draft: "Draft",
    exported: "Exported",
    reviewed: "Reviewed"
  };
  return labels[status];
}
