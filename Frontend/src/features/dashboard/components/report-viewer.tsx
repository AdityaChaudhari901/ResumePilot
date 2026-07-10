import {
  AlertTriangle,
  Bot,
  CheckCircle2,
  ChevronDown,
  CircleAlert,
  CircleCheck,
  CircleX,
  ClipboardList,
  Download,
  FileCheck2,
  GitBranch,
  ListChecks,
  SearchCheck,
  ShieldCheck
} from "lucide-react";
import type { ReactNode } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Panel } from "@/components/ui/panel";
import { EvidenceIdBadges } from "@/features/dashboard/components/evidence-id-badges";
import { MatchScoreBreakdownView } from "@/features/dashboard/components/match-score-breakdown";
import { ReportCoverLetterPanel } from "@/features/dashboard/components/report-cover-letter-panel";
import { ReportInterviewPrepPanel } from "@/features/dashboard/components/report-interview-prep-panel";
import type {
  AgentStepName,
  AgentStepStatus,
  AgentWorkflowMode,
  AgentWorkflowTrace,
  ApplicationReport,
  JobAnalysisResponse,
  ReportExportFormat,
  ResumeProfile,
  ValidationStatus,
  ValidationWarning
} from "@/features/dashboard/types";
import { formatScore, scoreLabel, scoreTone } from "@/features/dashboard/utils/report";

interface ReportViewerProps {
  analysis: JobAnalysisResponse | null;
  canOpenTailoredResume: boolean;
  isExporting: ReportExportFormat | null;
  onExport: (format: ReportExportFormat) => Promise<void>;
  onOpenTailoredResume: () => void;
  report: ApplicationReport | null;
  resumeProfile: ResumeProfile | null;
  workflowTrace: AgentWorkflowTrace | null;
}

export function ReportViewer({
  analysis,
  canOpenTailoredResume,
  isExporting,
  onExport,
  onOpenTailoredResume,
  report,
  resumeProfile,
  workflowTrace
}: ReportViewerProps) {
  if (!report || !analysis) {
    return (
      <Panel eyebrow="Step 05" title="Report">
        <div className="flex min-h-80 items-center justify-center rounded-md border border-dashed border-border bg-surface p-6 text-center">
          <div>
            <ClipboardList className="mx-auto h-8 w-8 text-muted-foreground" aria-hidden="true" />
            <p className="mt-3 text-sm font-medium text-foreground">No analysis yet</p>
            <p className="mt-1 text-sm text-muted-foreground">
              Add a job URL or paste the description, upload a resume, and run AI analysis.
            </p>
          </div>
        </div>
      </Panel>
    );
  }

  const matchTone = scoreTone(report.match_score);
  const hasUnclearJobRequirements = report.validation_warnings.some(
    (warning) => warning.code === "required_skills_unclear"
  );
  const hasProvisionalScore =
    hasUnclearJobRequirements || report.score_status === "provisional";
  const usesEvidenceV2 =
    report.scoring_version === "evidence_v2" ||
    report.score_breakdown?.scoring_version === "evidence_v2";
  const displayedScoringVersion =
    report.score_breakdown?.scoring_version ?? report.scoring_version;
  const scoreHeading = usesEvidenceV2
    ? hasProvisionalScore
      ? "Provisional evidence-fit score"
      : "Evidence-fit score"
    : displayedScoringVersion === "deterministic_v1"
      ? hasProvisionalScore
        ? "Provisional deterministic v1 score"
        : "Deterministic v1 score"
      : hasProvisionalScore
        ? "Provisional legacy score"
        : "Legacy unversioned score";
  const scoreBadgeTone = hasUnclearJobRequirements
    ? "danger"
    : hasProvisionalScore
      ? "warning"
      : usesEvidenceV2
        ? matchTone
        : "neutral";
  const scoreBadgeLabel = hasUnclearJobRequirements
    ? "Needs job details"
    : hasProvisionalScore
      ? usesEvidenceV2
        ? "Provisional — evidence incomplete"
        : "Historical score — provisional"
      : usesEvidenceV2
        ? scoreLabel(report.match_score)
        : "Historical score";
  const topKeywords = report.ats_keywords.slice(0, 10);
  const validationStatus = reportValidationStatus(report);
  const coverLetterWarnings = report.validation_warnings.filter((warning) =>
    warning.code.startsWith("cover_letter")
  );
  const interviewWarnings = report.validation_warnings.filter((warning) =>
    warning.code.startsWith("interview")
  );

  return (
    <Panel
      action={
        <div className="flex flex-wrap items-center justify-end gap-2">
          <Badge tone={validationStatusTone(validationStatus)}>
            Validation: {validationStatusLabel(validationStatus)}
          </Badge>
          <ReportExportButton
            icon={<Download className="h-4 w-4" aria-hidden="true" />}
            isExporting={isExporting === "markdown"}
            isUnavailable={Boolean(isExporting)}
            label="Markdown"
            onClick={() => void onExport("markdown")}
            variant="secondary"
          >
            Markdown
          </ReportExportButton>
          <Button
            disabled={!canOpenTailoredResume}
            icon={<FileCheck2 className="h-4 w-4" aria-hidden="true" />}
            onClick={onOpenTailoredResume}
            title={
              canOpenTailoredResume
                ? undefined
                : "Tailoring is unavailable because this report is not linked to an application."
            }
          >
            Review tailored resume
          </Button>
        </div>
      }
      eyebrow={`Report ${analysis.report_id}`}
      title="Evidence-backed fit"
    >
      <div className="space-y-5">
        <div className="grid gap-3 md:grid-cols-[12rem_1fr]">
          <div className="rounded-lg border border-border bg-surface p-4">
            <p className="text-xs font-semibold uppercase tracking-normal text-muted-foreground">
              {scoreHeading}
            </p>
            <p className="mt-2 font-mono text-5xl font-semibold tabular-nums">
              {formatScore(report.match_score)}
            </p>
            <Badge className="mt-3" tone={scoreBadgeTone}>
              {scoreBadgeLabel}
            </Badge>
            <p className="mt-3 text-xs leading-5 text-muted-foreground">
              This deterministic comparison is not a hiring probability or ATS guarantee.
            </p>
          </div>
          <div className="rounded-lg border border-border bg-surface p-4">
            <p className="text-sm font-semibold">Executive summary</p>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">{report.executive_summary}</p>
          </div>
        </div>

        <MatchScoreBreakdownView
          breakdown={report.score_breakdown}
          scoringVersion={report.scoring_version}
        />

        {hasUnclearJobRequirements ? (
          <div
            className="rounded-lg border border-warning/25 bg-warning/10 p-4"
            role="status"
          >
            <div className="flex gap-3">
              <AlertTriangle
                className="mt-0.5 h-5 w-5 shrink-0 text-warning"
                aria-hidden="true"
              />
              <div>
                <p className="text-sm font-semibold text-foreground">
                  Job details need review
                </p>
                <p className="mt-1 text-sm leading-6 text-muted-foreground">
                  ResumePilot could not extract explicit required skills from this listing. Use
                  a direct public job-detail URL with visible requirements, then rerun the
                  analysis before tailoring or exporting the resume.
                </p>
              </div>
            </div>
          </div>
        ) : null}

        <div className="grid gap-3 md:grid-cols-3">
          <Metric label="Matched" value={report.matched_skills.length} />
          <Metric label="Missing" value={report.missing_skills.length} />
          <Metric label="Warnings" value={report.validation_warnings.length} />
        </div>

        <WorkflowTracePanel trace={workflowTrace} />

        <section className="grid gap-4 lg:grid-cols-2">
          <div>
            <div className="mb-3 flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-validation" aria-hidden="true" />
              <h3 className="text-sm font-semibold">Matched skills</h3>
            </div>
            <div className="space-y-2">
              {report.matched_skills.slice(0, 8).map((item) => (
                <div className="rounded-md border border-border bg-surface p-3" key={item.skill}>
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-sm font-medium">{item.skill}</p>
                    <div className="flex shrink-0 flex-wrap justify-end gap-2">
                      <Badge tone="success">{item.match_type}</Badge>
                      <Badge tone={confidenceTone(item.confidence)}>
                        {item.confidence} confidence
                      </Badge>
                    </div>
                  </div>
                  <p className="mt-2 line-clamp-2 text-xs text-muted-foreground">
                    {item.job_evidence_text}
                  </p>
                  <EvidenceIdBadges evidenceIds={item.resume_evidence_ids} />
                </div>
              ))}
              {report.matched_skills.length === 0 ? (
                <EmptyReportState
                  tone={hasUnclearJobRequirements ? "warning" : "neutral"}
                  title="No evidence-backed matches yet"
                >
                  {hasUnclearJobRequirements
                    ? "No matches can be trusted until the job requirements are extracted."
                    : "No resume evidence matched the extracted job skills."}
                </EmptyReportState>
              ) : null}
            </div>
          </div>

          <div>
            <div className="mb-3 flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-warning" aria-hidden="true" />
              <h3 className="text-sm font-semibold">Missing or weak</h3>
            </div>
            <div className="space-y-2">
              {report.missing_skills.slice(0, 5).map((item) => (
                <div className="rounded-md border border-border bg-surface p-3" key={item.skill}>
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-sm font-medium">{item.skill}</p>
                    <Badge tone={item.importance === "required" ? "danger" : "warning"}>
                      {item.importance}
                    </Badge>
                  </div>
                  <p className="mt-2 text-xs text-muted-foreground">{item.recommendation}</p>
                </div>
              ))}
              {report.weak_skills.slice(0, 5).map((item) => (
                <div className="rounded-md border border-border bg-surface p-3" key={item.skill}>
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-sm font-medium">{item.skill}</p>
                    <Badge tone="warning">weak evidence</Badge>
                  </div>
                  <p className="mt-2 text-xs text-muted-foreground">{item.reason}</p>
                  <EvidenceIdBadges evidenceIds={item.resume_evidence_ids} />
                </div>
              ))}
              {report.missing_skills.length === 0 && report.weak_skills.length === 0 && (
                <EmptyReportState
                  tone={hasUnclearJobRequirements ? "warning" : "neutral"}
                  title={
                    hasUnclearJobRequirements ? "Gaps not available" : "No gaps detected"
                  }
                >
                  {hasUnclearJobRequirements
                    ? "Missing skills cannot be determined until explicit job requirements are extracted."
                    : "No missing or weak skills were found in the extracted job evidence."}
                </EmptyReportState>
              )}
            </div>
          </div>
        </section>

        <section>
          <div className="mb-3 flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-primary" aria-hidden="true" />
            <h3 className="text-sm font-semibold">Tailored bullets</h3>
          </div>
          <div className="space-y-2">
            {report.tailored_bullets.map((item) => (
              <div className="rounded-md border border-border bg-surface p-3" key={item.bullet}>
                <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                  <p className="text-sm leading-6">{item.bullet}</p>
                  {item.unsupported_claims.length > 0 ? (
                    <Badge className="shrink-0" tone="warning">
                      review only
                    </Badge>
                  ) : null}
                </div>
                <EvidenceIdBadges evidenceIds={item.evidence_ids} />
                {item.jd_keywords_used.length > 0 ? (
                  <p className="mt-2 text-xs text-muted-foreground">
                    Uses JD keywords: {item.jd_keywords_used.join(", ")}
                  </p>
                ) : null}
              </div>
            ))}
            {report.tailored_bullets.length === 0 ? (
              <div className="rounded-md border border-border bg-surface p-3 text-sm text-muted-foreground">
                No project or experience evidence was strong enough for an exportable tailored
                bullet. Add truthful project/work evidence before editing the resume.
              </div>
            ) : null}
          </div>
        </section>

        <section className="grid gap-4 lg:grid-cols-2">
          <div>
            <div className="mb-3 flex items-center gap-2">
              <SearchCheck className="h-4 w-4 text-primary" aria-hidden="true" />
              <h3 className="text-sm font-semibold">ATS keywords</h3>
            </div>
            <div className="space-y-2">
              {topKeywords.map((item) => (
                <div className="rounded-md border border-border bg-surface p-3" key={item.keyword}>
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-sm font-medium">{item.keyword}</p>
                    <Badge tone={keywordStatusTone(item.status)}>
                      {keywordStatusLabel(item.status)}
                    </Badge>
                  </div>
                  <p className="mt-2 text-xs text-muted-foreground">{item.note}</p>
                  <EvidenceIdBadges evidenceIds={item.evidence_ids} />
                </div>
              ))}
              {topKeywords.length === 0 ? (
                <EmptyReportState
                  tone={hasUnclearJobRequirements ? "warning" : "neutral"}
                  title="No ATS keywords extracted"
                >
                  {hasUnclearJobRequirements
                    ? "The job page did not expose enough requirement evidence for safe keyword suggestions."
                    : "No supported or add-only-if-true keywords were produced for this report."}
                </EmptyReportState>
              ) : null}
            </div>
          </div>

          <div>
            <div className="mb-3 flex items-center gap-2">
              <ListChecks className="h-4 w-4 text-validation" aria-hidden="true" />
              <h3 className="text-sm font-semibold">Next actions</h3>
            </div>
            <ol className="space-y-2">
              {report.next_actions.map((action) => (
                <li
                  className="rounded-md border border-border bg-surface p-3 text-sm leading-6 text-muted-foreground"
                  key={action}
                >
                  {action}
                </li>
              ))}
            </ol>
          </div>
        </section>

        <section className="grid gap-4 xl:grid-cols-2" aria-label="Application materials">
          <ReportCoverLetterPanel
            coverLetter={report.cover_letter}
            evidenceIds={report.cover_letter_evidence_ids ?? []}
            resumeProfile={resumeProfile}
            warnings={coverLetterWarnings}
          />
          <ReportInterviewPrepPanel
            groups={report.interview_questions}
            resumeProfile={resumeProfile}
            warnings={interviewWarnings}
          />
        </section>

        {report.validation_warnings.length > 0 ? (
          <section>
            <div className="mb-3 flex items-center gap-2">
              <CircleAlert className="h-4 w-4 text-warning" aria-hidden="true" />
              <h3 className="text-sm font-semibold">Validation warnings</h3>
            </div>
            <div className="space-y-2">
              {report.validation_warnings.map((warning) => (
                <div className="rounded-md border border-border bg-surface p-3" key={warning.code}>
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone={validationSeverityTone(warning)}>
                      {validationSeverityLabel(warning)}
                    </Badge>
                    <span className="font-mono text-xs text-muted-foreground">{warning.code}</span>
                  </div>
                  <p className="mt-2 text-xs leading-5 text-muted-foreground">
                    {warning.message}
                  </p>
                  <EvidenceIdBadges evidenceIds={warning.evidence_ids} />
                </div>
              ))}
            </div>
          </section>
        ) : null}
      </div>
    </Panel>
  );
}

function ReportExportButton({
  children,
  icon,
  isExporting,
  isUnavailable,
  label,
  onClick,
  variant
}: {
  children: string;
  icon: ReactNode;
  isExporting: boolean;
  isUnavailable: boolean;
  label: string;
  onClick: () => void;
  variant: "primary" | "secondary";
}) {
  return (
    <Button
      aria-label={`Download ${label}`}
      disabled={isUnavailable}
      icon={icon}
      onClick={onClick}
      variant={variant}
    >
      {isExporting ? "Preparing…" : children}
    </Button>
  );
}

interface MetricProps {
  label: string;
  value: number;
}

function Metric({ label, value }: MetricProps) {
  return (
    <div className="rounded-md border border-border bg-surface p-3">
      <p className="text-xs font-semibold uppercase tracking-normal text-muted-foreground">{label}</p>
      <p className="mt-2 font-mono text-2xl font-semibold tabular-nums">{value}</p>
    </div>
  );
}

function EmptyReportState({
  children,
  title,
  tone
}: {
  children: string;
  title: string;
  tone: "neutral" | "warning";
}) {
  const toneClass =
    tone === "warning"
      ? "border-warning/25 bg-warning/10"
      : "border-border bg-surface";

  return (
    <div className={`rounded-md border p-3 ${toneClass}`}>
      <p className="text-sm font-medium text-foreground">{title}</p>
      <p className="mt-1 text-sm leading-6 text-muted-foreground">{children}</p>
    </div>
  );
}

function confidenceTone(confidence: ApplicationReport["matched_skills"][number]["confidence"]) {
  if (confidence === "high") {
    return "success";
  }
  if (confidence === "low") {
    return "warning";
  }
  return "neutral";
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
    return "Blocked";
  }
  return status === "warn" ? "Needs review" : "Passed";
}

function validationSeverityTone(
  warning: ValidationWarning
): "success" | "warning" | "danger" {
  return validationStatusTone(warning.severity ?? "warn");
}

function validationSeverityLabel(warning: ValidationWarning): string {
  return validationStatusLabel(warning.severity ?? "warn");
}

interface WorkflowTracePanelProps {
  trace: AgentWorkflowTrace | null;
}

const STEP_LABELS: Record<AgentStepName, string> = {
  jd_parser: "JD parser",
  crewai_runtime: "Live AI runtime",
  langgraph_runtime: "LangGraph runtime",
  human_approval: "Human approval",
  resume_match: "Resume match",
  ats_optimizer: "ATS optimizer",
  cover_letter: "Cover letter",
  interview_coach: "Interview coach",
  validation_gate: "Validation gate"
};

function WorkflowTracePanel({ trace }: WorkflowTracePanelProps) {
  if (!trace) {
    return null;
  }

  const completedSteps = trace.steps.filter((step) => step.status === "completed").length;
  const totalDuration = formatDuration(trace.duration_ms);
  const hasRuntimeMetadata = Boolean(
    trace.provider ??
      trace.model ??
      trace.token_usage ??
      (trace.cost_estimate_usd !== null && trace.cost_estimate_usd !== undefined)
  );

  return (
    <details
      aria-labelledby="workflow-trace-title"
      className="group rounded-lg border border-border bg-surface"
    >
      <summary className="flex cursor-pointer list-none flex-col gap-3 p-4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/35 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex min-w-0 items-start gap-2">
          {trace.mode !== "deterministic_fallback" ? (
            <Bot className="mt-0.5 h-4 w-4 shrink-0 text-primary" aria-hidden="true" />
          ) : (
            <GitBranch
              className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground"
              aria-hidden="true"
            />
          )}
          <div className="min-w-0">
            <h3 id="workflow-trace-title" className="text-sm font-semibold">
              Workflow trace
            </h3>
            <p className="mt-1 text-xs text-muted-foreground">
              {completedSteps}/{trace.steps.length} steps completed
              {totalDuration ? ` · ${totalDuration} total` : ""}
            </p>
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <Badge tone={validationStatusTone(trace.validation_status ?? "pass")}>
            {validationStatusLabel(trace.validation_status ?? "pass")}
          </Badge>
          <Badge tone={workflowModeTone(trace.mode)}>{workflowModeLabel(trace.mode)}</Badge>
          <ChevronIndicator />
        </div>
      </summary>

      <div className="border-t border-border p-4 pt-0">

      {hasRuntimeMetadata ? (
        <div className="pt-4">
          <h4 className="text-xs font-semibold uppercase tracking-normal text-muted-foreground">
            Runtime
          </h4>
          <dl className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <TraceRuntimeMetric label="Provider" value={trace.provider ?? "Not reported"} />
            <TraceRuntimeMetric label="Model" value={trace.model ?? "Not reported"} />
            <TraceRuntimeMetric label="Tokens" value={formatTokenUsage(trace.token_usage)} />
            <TraceRuntimeMetric label="Cost" value={formatCost(trace.cost_estimate_usd)} />
          </dl>
        </div>
      ) : null}

      <div className="mt-4 space-y-2">
        {trace.steps.map((step, index) => {
          const stepDuration = formatDuration(step.duration_ms);

          return (
            <div
              className="flex min-w-0 gap-3 rounded-md border border-border bg-background p-3"
              key={`${step.name}-${index}`}
            >
              <StepStatusIcon status={step.status} />
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="text-sm font-medium">{STEP_LABELS[step.name]}</p>
                  <Badge tone={stepStatusTone(step.status)}>{stepStatusLabel(step.status)}</Badge>
                  {stepDuration ? (
                    <span className="font-mono text-xs text-muted-foreground">
                      {stepDuration}
                    </span>
                  ) : null}
                </div>
                <p className="mt-1 break-words text-xs leading-5 text-muted-foreground">
                  {step.summary}
                </p>
              </div>
            </div>
          );
        })}
      </div>

      {trace.validation_warning_codes.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {trace.validation_warning_codes.map((code) => (
            <Badge key={code} tone="warning">
              {code}
            </Badge>
          ))}
        </div>
      )}
      </div>
    </details>
  );
}

function ChevronIndicator() {
  return (
    <ChevronDown
      aria-hidden="true"
      className="h-4 w-4 text-muted-foreground transition-transform group-open:rotate-180"
    />
  );
}

function TraceRuntimeMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="mt-1 break-words font-mono text-xs text-foreground">{value}</dd>
    </div>
  );
}

function StepStatusIcon({ status }: { status: AgentStepStatus }) {
  if (status === "completed") {
    return (
      <CircleCheck className="mt-0.5 h-4 w-4 shrink-0 text-validation" aria-hidden="true" />
    );
  }
  if (status === "failed") {
    return (
      <CircleX className="mt-0.5 h-4 w-4 shrink-0 text-destructive" aria-hidden="true" />
    );
  }
  return <CircleAlert className="mt-0.5 h-4 w-4 shrink-0 text-warning" aria-hidden="true" />;
}

function workflowModeLabel(mode: AgentWorkflowMode): string {
  return mode === "deterministic_fallback" ? "Deterministic fallback" : "Live AI workflow";
}

function workflowModeTone(mode: AgentWorkflowMode): "neutral" | "primary" {
  return mode === "deterministic_fallback" ? "neutral" : "primary";
}

function stepStatusLabel(status: AgentStepStatus): string {
  if (status === "completed") {
    return "Completed";
  }
  if (status === "failed") {
    return "Failed";
  }
  return "Degraded";
}

function stepStatusTone(status: AgentStepStatus): "success" | "warning" | "danger" {
  if (status === "completed") {
    return "success";
  }
  if (status === "failed") {
    return "danger";
  }
  return "warning";
}

function formatDuration(durationMs: number | null | undefined): string | null {
  if (durationMs === null || durationMs === undefined) {
    return null;
  }
  if (durationMs < 1000) {
    return `${durationMs} ms`;
  }
  const seconds = durationMs / 1000;
  return `${seconds >= 10 ? seconds.toFixed(0) : seconds.toFixed(1)} s`;
}

function formatTokenUsage(tokenUsage: AgentWorkflowTrace["token_usage"]): string {
  if (!tokenUsage || tokenUsage.total_tokens <= 0) {
    return "Not available";
  }
  const requests =
    tokenUsage.successful_requests > 0 ? ` · ${tokenUsage.successful_requests} req` : "";
  return `${tokenUsage.total_tokens.toLocaleString()} total${requests}`;
}

function formatCost(costEstimateUsd: number | null | undefined): string {
  if (costEstimateUsd === null || costEstimateUsd === undefined) {
    return "Not available";
  }
  return `$${costEstimateUsd.toFixed(6)}`;
}

function keywordStatusLabel(status: ApplicationReport["ats_keywords"][number]["status"]): string {
  if (status === "add_only_if_true") {
    return "add only if true";
  }
  return status;
}

function keywordStatusTone(
  status: ApplicationReport["ats_keywords"][number]["status"]
): "success" | "warning" | "neutral" {
  if (status === "supported") {
    return "success";
  }
  if (status === "add_only_if_true") {
    return "warning";
  }
  return "neutral";
}
