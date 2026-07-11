import {
  ArrowRight,
  BriefcaseBusiness,
  CheckCircle2,
  Circle,
  CircleDot,
  ClipboardList,
  FileCheck2,
  FileText,
  GitBranch,
  LockKeyhole,
  SearchCheck,
  ShieldCheck
} from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

import { Badge } from "@/components/ui/badge";
import { BentoGrid } from "@/components/ui/bento-grid";
import { Panel } from "@/components/ui/panel";
import type {
  AgentWorkflowTrace,
  ApplicationItem,
  ApplicationReport,
  JobAnalysisResponse,
  JobSourceType,
  ResumeProfile,
  TailoredResumeDraft,
  ValidationStatus
} from "@/features/dashboard/types";
import type {
  WorkflowProgressStep,
  WorkflowStepStatus
} from "@/features/dashboard/components/workflow-progress";
import {
  formatScore,
  reportScorePresentation,
  scoreMetricLabel
} from "@/features/dashboard/utils/report";
import { cn } from "@/lib/cn";

interface ApplicationCaseOverviewProps {
  analysis: JobAnalysisResponse;
  application: ApplicationItem | null;
  applicationId: number;
  jobSourceType: JobSourceType;
  report: ApplicationReport;
  resumeProfile: ResumeProfile | null;
  tailoredResumeDraft: TailoredResumeDraft | null;
  tailoredResumeState: TailoredResumeState;
  workflowSteps: WorkflowProgressStep[];
  workflowTrace: AgentWorkflowTrace | null;
}

const primaryLinkClasses =
  "inline-flex min-h-10 items-center justify-center gap-2 rounded-lg border border-primary bg-primary px-4 text-sm font-bold tracking-[-0.01em] text-primary-foreground shadow-[0_8px_24px_-14px_color-mix(in_srgb,var(--color-primary)_85%,transparent)] transition-[filter,transform] hover:brightness-95 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background active:translate-y-px";

const secondaryLinkClasses =
  "inline-flex min-h-10 items-center justify-center gap-2 rounded-lg border border-background/25 bg-background/10 px-4 text-sm font-bold tracking-[-0.01em] text-background transition-[background-color,border-color,transform] hover:border-background/45 hover:bg-background/15 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-foreground active:translate-y-px";

const surfaceLinkClasses =
  "inline-flex min-h-10 items-center justify-center gap-2 rounded-lg border border-border-strong bg-surface-raised px-4 text-sm font-bold tracking-[-0.01em] text-foreground transition-[background-color,border-color,transform] hover:border-foreground/30 hover:bg-surface focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background active:translate-y-px";

export function ApplicationCaseOverview({
  analysis,
  application,
  applicationId,
  jobSourceType,
  report,
  resumeProfile,
  tailoredResumeDraft,
  tailoredResumeState,
  workflowSteps,
  workflowTrace
}: ApplicationCaseOverviewProps) {
  const reportHref = `/app/applications/${applicationId}/report`;
  const resumeHref = `/app/applications/${applicationId}/resume`;
  const validationStatus = reportValidationStatus(report);
  const scorePresentation = reportScorePresentation(report);
  const gapCount = report.missing_skills.length + report.weak_skills.length;
  const matchedSkills = report.matched_skills.slice(0, 5);
  const visibleGaps = [
    ...report.missing_skills.map((skill) => skill.skill),
    ...report.weak_skills.map((skill) => skill.skill)
  ].slice(0, 3);
  const verifiedDraft =
    tailoredResumeState === "ready" && tailoredResumeDraft ? tailoredResumeDraft : null;
  const resolvedDraftState: TailoredResumeState = verifiedDraft
    ? "ready"
    : tailoredResumeState === "loading"
      ? "loading"
      : "unavailable";
  const decision = caseDecision(verifiedDraft, resolvedDraftState);

  return (
    <BentoGrid
      aria-label="Application case overview"
      className="auto-rows-auto sm:grid-cols-2 xl:grid-cols-12"
      role="region"
    >
      <article
        className="relative overflow-hidden rounded-2xl border border-foreground bg-foreground p-5 text-background shadow-[0_24px_70px_-46px_rgba(8,12,7,0.95)] sm:col-span-2 sm:p-7 lg:col-span-1 xl:col-span-7"
        data-testid="case-next-action"
      >
        <div
          aria-hidden="true"
          className="absolute inset-y-0 right-0 w-32 bg-[radial-gradient(circle_at_center,color-mix(in_srgb,var(--color-primary)_20%,transparent),transparent_68%)]"
        />
        <div className="relative">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-[0.68rem] font-semibold uppercase tracking-[0.16em] text-background/60">
              Next decision
            </span>
            <Badge
              className="border-background/25 bg-background text-foreground"
              tone={validationStatusTone(validationStatus)}
            >
              Validation {validationStatusLabel(validationStatus)}
            </Badge>
            {application ? (
              <span className="rounded-full border border-background/20 bg-background/10 px-2.5 py-1 font-mono text-[0.68rem] font-medium capitalize text-background/75">
                {application.status}
              </span>
            ) : null}
          </div>
          <h2 className="mt-6 max-w-2xl text-2xl font-extrabold tracking-[-0.045em] text-background sm:text-3xl">
            {decision.title}
          </h2>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-background/70">
            {decision.description}
          </p>
          <div className="mt-6 flex flex-col gap-2 sm:flex-row sm:flex-wrap">
            <Link
              className={primaryLinkClasses}
              href={decision.primaryHref === "resume" ? resumeHref : reportHref}
            >
              {decision.primaryLabel}
              <ArrowRight className="h-4 w-4" aria-hidden="true" />
            </Link>
            {decision.secondaryLabel ? (
              <Link
                className={secondaryLinkClasses}
                href={decision.primaryHref === "resume" ? reportHref : resumeHref}
              >
                {decision.secondaryLabel}
              </Link>
            ) : null}
          </div>
        </div>
      </article>

      <Panel
        action={
          <Badge tone={scorePresentation.badgeTone}>{scorePresentation.badgeLabel}</Badge>
        }
        as="article"
        className="sm:col-span-2 lg:col-span-1 xl:col-span-5"
        data-testid="case-score"
        eyebrow="Fit signal"
        title={scorePresentation.heading}
      >
        <div className="flex items-end justify-between gap-4">
          <p className="font-mono text-6xl font-semibold tracking-[-0.08em] text-foreground tabular-nums">
            {formatScore(report.match_score)}
          </p>
          <p className="pb-2 text-right font-mono text-[0.68rem] uppercase tracking-[0.12em] text-muted-foreground">
            Report {analysis.report_id}
          </p>
        </div>
        <div className="mt-5 h-2 overflow-hidden rounded-full bg-surface-inset" aria-hidden="true">
          <div
            className="h-full rounded-full bg-primary"
            style={{ width: `${Math.max(0, Math.min(100, report.match_score))}%` }}
          />
        </div>
        <p className="mt-4 text-sm leading-6 text-muted-foreground">
          {scoreMetricLabel(
            report.score_breakdown?.scoring_version ?? report.scoring_version,
            report.score_status
          )}. This comparison measures linked evidence, not hiring probability or an ATS guarantee.
        </p>
      </Panel>

      <Panel
        action={<Badge tone="success">Evidence linked</Badge>}
        as="article"
        className="sm:col-span-2 lg:col-span-1 xl:col-span-4"
        eyebrow="Source ledger"
        title="Evidence snapshot"
      >
        <dl className="grid grid-cols-2 gap-2">
          <CaseMetric label="Matched" value={report.matched_skills.length} />
          <CaseMetric label="Gaps" value={gapCount} />
          <CaseMetric label="Resume facts" value={resumeProfile?.facts.length ?? 0} />
          <CaseMetric label="Warnings" value={report.validation_warnings.length} />
        </dl>
        <div className="mt-4 space-y-2 border-t border-border pt-4 text-xs text-muted-foreground">
          <CaseMetadata
            icon={<FileText className="h-4 w-4 text-primary" aria-hidden="true" />}
            label="Candidate"
            value={resumeProfile?.candidate.name ?? "Resume evidence parsed"}
          />
          <CaseMetadata
            icon={<BriefcaseBusiness className="h-4 w-4 text-primary" aria-hidden="true" />}
            label="Job source"
            value={jobSourceType === "pasted_text" ? "Reviewed description" : "Reviewed job URL"}
          />
          <CaseMetadata
            icon={<GitBranch className="h-4 w-4 text-primary" aria-hidden="true" />}
            label="Workflow"
            value={workflowModeLabel(workflowTrace)}
          />
        </div>
      </Panel>

      <Panel
        action={<Badge tone="primary">6-stage proof chain</Badge>}
        as="article"
        className="sm:col-span-2 lg:col-span-1 xl:col-span-8"
        eyebrow="Case progression"
        title="Every gate stays visible"
      >
        <ol className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {workflowSteps.map((step, index) => (
            <Milestone key={step.id} index={index} step={step} />
          ))}
        </ol>
      </Panel>

      <Panel
        action={<Badge tone={validationStatusTone(validationStatus)}>Report {analysis.report_id}</Badge>}
        as="article"
        className="sm:col-span-2 lg:col-span-1 xl:col-span-7"
        eyebrow="Validated output"
        title="Fit report"
      >
        <p className="line-clamp-4 text-sm leading-7 text-muted-foreground">
          {report.executive_summary}
        </p>
        <div className="mt-5 grid gap-4 border-t border-border pt-5 sm:grid-cols-2">
          <EvidenceGroup
            emptyLabel="No evidence-backed matches"
            icon={<SearchCheck className="h-4 w-4 text-validation" aria-hidden="true" />}
            items={matchedSkills.map((skill) => skill.skill)}
            label="Strongest matches"
            tone="success"
          />
          <EvidenceGroup
            emptyLabel="No identified skill gaps"
            icon={<ShieldCheck className="h-4 w-4 text-warning" aria-hidden="true" />}
            items={visibleGaps}
            label="Review before applying"
            tone={visibleGaps.length > 0 ? "warning" : "success"}
          />
        </div>
        <Link className={cn(surfaceLinkClasses, "mt-5 w-full sm:w-auto")} href={reportHref}>
          <ClipboardList className="h-4 w-4" aria-hidden="true" />
          Open full evidence report
        </Link>
      </Panel>

      <Panel
        action={
          <Badge tone={draftStateTone(resolvedDraftState, verifiedDraft)}>
            {draftStateLabel(resolvedDraftState, verifiedDraft)}
          </Badge>
        }
        as="article"
        className="sm:col-span-2 lg:col-span-1 xl:col-span-5"
        eyebrow="Approval desk"
        title="Tailored resume"
      >
        {verifiedDraft ? (
          <>
            <dl className="grid grid-cols-3 gap-2">
              <CaseMetric label="Accepted" value={verifiedDraft.accepted_count} />
              <CaseMetric label="Pending" value={verifiedDraft.pending_count} />
              <CaseMetric label="Rejected" value={verifiedDraft.rejected_count} />
            </dl>
            <div className="mt-5 rounded-xl border border-primary/25 bg-primary/8 p-4">
              <div className="flex gap-3">
                <FileCheck2 className="mt-0.5 h-5 w-5 shrink-0 text-primary" aria-hidden="true" />
                <div>
                  <p className="text-sm font-semibold text-foreground">
                    Export uses approved evidence only
                  </p>
                  <p className="mt-1 text-xs leading-5 text-muted-foreground">
                    Review every proposed bullet before DOCX, LaTeX, or PDF becomes available.
                  </p>
                </div>
              </div>
            </div>
            <Link className={cn(primaryLinkClasses, "mt-5 w-full")} href={resumeHref}>
              Review tailored resume
              <ArrowRight className="h-4 w-4" aria-hidden="true" />
            </Link>
          </>
        ) : (
          <DraftVerificationState
            state={resolvedDraftState === "loading" ? "loading" : "unavailable"}
          />
        )}
      </Panel>
    </BentoGrid>
  );
}

function CaseMetric({ label, value }: { label: string; value: number }) {
  return (
    <div className="min-w-0 rounded-xl border border-border bg-surface p-3">
      <dt className="text-[0.7rem] leading-4 text-muted-foreground">{label}</dt>
      <dd className="mt-1 font-mono text-2xl font-semibold tracking-[-0.04em] text-foreground tabular-nums">
        {value}
      </dd>
    </div>
  );
}

function CaseMetadata({ icon, label, value }: { icon: ReactNode; label: string; value: string }) {
  return (
    <div className="flex min-w-0 items-center gap-2">
      {icon}
      <span className="shrink-0 font-medium text-foreground">{label}</span>
      <span aria-hidden="true">·</span>
      <span className="truncate">{value}</span>
    </div>
  );
}

function EvidenceGroup({
  emptyLabel,
  icon,
  items,
  label,
  tone
}: {
  emptyLabel: string;
  icon: ReactNode;
  items: string[];
  label: string;
  tone: "success" | "warning";
}) {
  return (
    <section>
      <div className="flex items-center gap-2">
        {icon}
        <h3 className="text-sm font-semibold text-foreground">{label}</h3>
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        {items.length > 0 ? (
          items.map((item) => (
            <Badge key={item} tone={tone}>
              {item}
            </Badge>
          ))
        ) : (
          <p className="text-xs leading-5 text-muted-foreground">{emptyLabel}</p>
        )}
      </div>
    </section>
  );
}

function Milestone({ index, step }: { index: number; step: WorkflowProgressStep }) {
  return (
    <li
      className={cn(
        "rounded-xl border border-border bg-surface p-3.5",
        step.status === "active" && "border-primary/45 bg-primary/8",
        step.status === "complete" && "border-validation/25"
      )}
    >
      <div className="flex items-center justify-between gap-3">
        <span className="font-mono text-[0.65rem] font-medium tracking-[0.12em] text-muted-foreground">
          0{index + 1}
        </span>
        <MilestoneStatusIcon status={step.status} />
      </div>
      <p className="mt-3 text-sm font-bold tracking-[-0.02em] text-foreground">{step.label}</p>
      <p className="mt-1 line-clamp-1 text-xs leading-5 text-muted-foreground">{step.detail}</p>
      <p className={cn("mt-2 font-mono text-[0.62rem] uppercase tracking-[0.12em]", milestoneStatusClasses(step.status))}>
        {milestoneStatusLabel(step.status)}
      </p>
    </li>
  );
}

function MilestoneStatusIcon({ status }: { status: WorkflowStepStatus }) {
  const className = cn(
    "h-4 w-4 shrink-0 text-muted-foreground",
    status === "complete" && "text-validation",
    status === "active" && "text-primary"
  );
  if (status === "complete") {
    return <CheckCircle2 aria-hidden="true" className={className} />;
  }
  if (status === "active") {
    return <CircleDot aria-hidden="true" className={className} />;
  }
  if (status === "locked") {
    return <LockKeyhole aria-hidden="true" className={className} />;
  }
  return <Circle aria-hidden="true" className={className} />;
}

function milestoneStatusClasses(status: WorkflowStepStatus): string {
  if (status === "complete") {
    return "text-validation";
  }
  if (status === "active" || status === "ready") {
    return "text-accent";
  }
  return "text-muted-foreground";
}

function milestoneStatusLabel(status: WorkflowStepStatus): string {
  const labels: Record<WorkflowStepStatus, string> = {
    active: "Current",
    complete: "Verified",
    locked: "Locked",
    ready: "Ready"
  };
  return labels[status];
}

type TailoredResumeState = "loading" | "ready" | "unavailable";

function caseDecision(
  draft: TailoredResumeDraft | null,
  state: TailoredResumeState
): {
  description: string;
  primaryHref: "report" | "resume";
  primaryLabel: string;
  secondaryLabel?: string;
  title: string;
} {
  if (draft?.export_ready) {
    return {
      description:
        "Your accepted bullets passed the evidence gate. Open the approval desk to export the tailored resume or revisit the full fit analysis.",
      primaryHref: "resume",
      primaryLabel: "Open export-ready resume",
      secondaryLabel: "Open full report",
      title: "Your approved resume is ready to export."
    };
  }
  if (draft && draft.pending_count > 0) {
    return {
      description:
        "Compare every suggested bullet with its linked resume evidence. Only accepted claims can enter an exported resume.",
      primaryHref: "resume",
      primaryLabel: `Review ${draft.pending_count} pending ${draft.pending_count === 1 ? "change" : "changes"}`,
      secondaryLabel: "Open full report",
      title: "The fit report is complete. Your draft needs review."
    };
  }
  if (state === "loading") {
    return {
      description:
        "The fit report is verified. ResumePilot is still checking that the application-specific draft belongs to this report before exposing approval or export controls.",
      primaryHref: "report",
      primaryLabel: "Open full report",
      title: "Your report is ready. The tailored draft is being verified."
    };
  }
  if (state === "unavailable") {
    return {
      description:
        "The fit report is verified, but the application-specific draft could not be confirmed. Refresh the workspace before reviewing or exporting resume changes.",
      primaryHref: "report",
      primaryLabel: "Open full report",
      title: "Your report is ready. Draft approval remains locked."
    };
  }
  return {
    description:
      "Inspect the evidence-backed fit analysis, then review each proposed resume change before export.",
    primaryHref: "report",
    primaryLabel: "Open full report",
    secondaryLabel: "Review tailored resume",
    title: "Your evidence-backed case file is ready."
  };
}

function DraftVerificationState({ state }: { state: Exclude<TailoredResumeState, "ready"> }) {
  const isLoading = state === "loading";
  return (
    <div
      className={cn(
        "rounded-xl border p-4",
        isLoading
          ? "border-border bg-surface"
          : "border-warning/30 bg-warning/10"
      )}
      role="status"
    >
      <div className="flex gap-3">
        {isLoading ? (
          <SearchCheck className="mt-0.5 h-5 w-5 shrink-0 text-primary" aria-hidden="true" />
        ) : (
          <LockKeyhole className="mt-0.5 h-5 w-5 shrink-0 text-warning" aria-hidden="true" />
        )}
        <div>
          <p className="text-sm font-semibold text-foreground">
            {isLoading ? "Verifying the application draft" : "Draft approval is unavailable"}
          </p>
          <p className="mt-1 text-xs leading-5 text-muted-foreground">
            {isLoading
              ? "Approval counts and export controls stay hidden until report ownership is confirmed."
              : "Refresh workspace status to retry the protected draft lookup."}
          </p>
        </div>
      </div>
    </div>
  );
}

function draftStateTone(
  state: TailoredResumeState,
  draft: TailoredResumeDraft | null
): "neutral" | "success" | "warning" {
  if (state === "loading") {
    return "neutral";
  }
  if (state === "unavailable") {
    return "warning";
  }
  return draft?.export_ready ? "success" : "warning";
}

function draftStateLabel(state: TailoredResumeState, draft: TailoredResumeDraft | null): string {
  if (state === "loading") {
    return "Verifying";
  }
  if (state === "unavailable") {
    return "Unavailable";
  }
  return draft?.export_ready ? "Export ready" : "Approval required";
}

function reportValidationStatus(report: ApplicationReport): ValidationStatus {
  if (report.validation_status) {
    return report.validation_status;
  }
  if (report.validation_warnings.some((warning) => warning.severity === "block")) {
    return "block";
  }
  return report.validation_warnings.length > 0 ? "warn" : "pass";
}

function validationStatusTone(status: ValidationStatus): "success" | "warning" | "danger" {
  if (status === "block") {
    return "danger";
  }
  return status === "warn" ? "warning" : "success";
}

function validationStatusLabel(status: ValidationStatus): string {
  if (status === "block") {
    return "blocked";
  }
  return status === "warn" ? "needs review" : "passed";
}

function workflowModeLabel(trace: AgentWorkflowTrace | null): string {
  if (!trace) {
    return "Trace unavailable";
  }
  if (trace.mode === "deterministic_fallback") {
    return "Deterministic fallback";
  }
  if (trace.mode === "langgraph") {
    return "LangGraph reviewed workflow";
  }
  return "Historical workflow";
}
