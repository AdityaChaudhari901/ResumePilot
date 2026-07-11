import {
  AlertTriangle,
  Bot,
  ChevronDown,
  CircleAlert,
  CircleCheck,
  CircleX,
  ClipboardList,
  Download,
  FileCheck2,
  FileText,
  GitBranch,
  ListChecks,
  SearchCheck,
  ShieldCheck
} from "lucide-react";
import { useRef, type ReactNode } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Panel } from "@/components/ui/panel";
import { EvidenceIdBadges } from "@/features/dashboard/components/evidence-id-badges";
import { MatchScoreBreakdownView } from "@/features/dashboard/components/match-score-breakdown";
import { ReportCoverLetterPanel } from "@/features/dashboard/components/report-cover-letter-panel";
import { ReportInterviewPrepPanel } from "@/features/dashboard/components/report-interview-prep-panel";
import { ReportRecommendations } from "@/features/dashboard/components/report-recommendations";
import { ReportSectionDisclosure } from "@/features/dashboard/components/report-section-disclosure";
import { ReportSkillEvidence } from "@/features/dashboard/components/report-skill-evidence";
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
import { formatScore, reportScorePresentation } from "@/features/dashboard/utils/report";

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
  const materialsDisclosureRef = useRef<HTMLDetailsElement>(null);

  if (!report || !analysis) {
    return (
      <Panel eyebrow="Step 05" title="Report">
        <div className="flex min-h-80 items-center justify-center rounded-2xl border border-dashed border-border-strong bg-surface p-6 text-center">
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

  const hasUnclearJobRequirements = report.validation_warnings.some(
    (warning) => warning.code === "required_skills_unclear"
  );
  const {
    badgeLabel: scoreBadgeLabel,
    badgeTone: scoreBadgeTone,
    heading: scoreHeading
  } = reportScorePresentation(report);
  const matchedPreview = report.matched_skills.slice(0, 6);
  const missingPreview = report.missing_skills.slice(0, report.weak_skills.length > 0 ? 5 : 6);
  const gapPreview = [
    ...missingPreview.map((item) => ({
      label: item.importance,
      skill: item.skill,
      tone: item.importance === "required" ? ("danger" as const) : ("warning" as const)
    })),
    ...report.weak_skills.slice(0, 6 - missingPreview.length).map((item) => ({
      label: "weak evidence",
      skill: item.skill,
      tone: "warning" as const
    }))
  ].slice(0, 6);
  const keywordPreview = report.ats_keywords.slice(0, 8);
  const actionPreview = report.next_actions.slice(0, 3);
  const gapCount = report.missing_skills.length + report.weak_skills.length;
  const scoreDetailTitle = report.score_breakdown
    ? "How this evidence-fit score is calculated"
    : "About this historical score";
  const scoreDetailDescription = report.score_breakdown
    ? "Inspect weighting, contributions, caps, and the evidence behind every score component."
    : "Review the saved score provenance without implying that unrecorded components can be reconstructed.";
  const validationStatus = reportValidationStatus(report);
  const coverLetterWarnings = report.validation_warnings.filter((warning) =>
    warning.code.startsWith("cover_letter")
  );
  const interviewWarnings = report.validation_warnings.filter((warning) =>
    warning.code.startsWith("interview")
  );

  function revealCoverLetter() {
    const materialsDisclosure = materialsDisclosureRef.current;
    if (!materialsDisclosure) {
      return;
    }

    materialsDisclosure.open = true;
    const coverLetterDisclosure = materialsDisclosure.querySelector<HTMLDetailsElement>(
      '[data-testid="cover-letter-draft-disclosure"]'
    );
    if (coverLetterDisclosure) {
      coverLetterDisclosure.open = true;
    }

    window.requestAnimationFrame(() => {
      const target = coverLetterDisclosure?.querySelector<HTMLElement>("summary");
      target?.focus();
      target?.scrollIntoView({
        behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches
          ? "auto"
          : "smooth",
        block: "center"
      });
    });
  }

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
            icon={<FileText className="h-4 w-4" aria-hidden="true" />}
            onClick={revealCoverLetter}
            variant="secondary"
          >
            Open cover letter
          </Button>
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
      <div className="space-y-4">
        <section
          aria-label="Report decision brief"
          className="grid gap-px overflow-hidden rounded-2xl border border-border bg-border lg:grid-cols-[15rem_minmax(0,1fr)]"
        >
          <div className="bg-terminal p-5 text-white">
            <p className="font-mono text-[0.66rem] font-semibold uppercase tracking-[0.13em] text-white/60">
              {scoreHeading}
            </p>
            <p className="mt-3 font-mono text-6xl font-semibold tracking-[-0.08em] text-primary tabular-nums">
              {formatScore(report.match_score)}
            </p>
            <Badge
              className="mt-3 border-white/25 bg-white text-[#171a14]"
              tone={scoreBadgeTone}
            >
              {scoreBadgeLabel}
            </Badge>
            <p className="mt-4 text-xs leading-5 text-white/65">
              This deterministic comparison is not a hiring probability or ATS guarantee.
            </p>
          </div>
          <div className="min-w-0 bg-surface-raised p-5 sm:p-6">
            <p className="font-mono text-[0.66rem] font-semibold uppercase tracking-[0.13em] text-muted-foreground">
              Decision brief
            </p>
            <p className="mt-3 text-sm leading-7 text-muted-foreground">
              {report.executive_summary}
            </p>
            <dl className="mt-5 grid grid-cols-2 gap-2 border-t border-border pt-4 sm:grid-cols-4">
              <ReportMetric label="Matched" value={report.matched_skills.length} />
              <ReportMetric label="Missing" value={report.missing_skills.length} />
              <ReportMetric label="Weak" value={report.weak_skills.length} />
              <ReportMetric label="Warnings" value={report.validation_warnings.length} />
            </dl>
          </div>
        </section>

        {hasUnclearJobRequirements ? (
          <div
            className="rounded-xl border border-warning/30 bg-warning/10 p-4"
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

        <section aria-label="Report at a glance" className="grid gap-3 xl:grid-cols-12">
          <article className="min-w-0 rounded-xl border border-border bg-surface p-4 sm:p-5 xl:col-span-7">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <SearchCheck className="h-4 w-4 text-validation" aria-hidden="true" />
                <h3 className="text-sm font-bold text-foreground">Matched skills</h3>
              </div>
              <Badge tone="success">{report.matched_skills.length} linked</Badge>
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              {matchedPreview.map((item) => (
                <Badge
                  aria-label={`${item.skill}, matched`}
                  className="max-w-full whitespace-normal [overflow-wrap:anywhere]"
                  key={item.skill}
                  tone="success"
                >
                  {item.skill}
                </Badge>
              ))}
              {report.matched_skills.length === 0 ? (
                <div>
                  <p className="text-sm font-semibold text-foreground">
                    No evidence-backed matches yet
                  </p>
                  <p className="mt-1 text-sm leading-6 text-muted-foreground">
                    {hasUnclearJobRequirements
                      ? "No matches can be trusted until the job requirements are extracted."
                      : "No resume evidence matched the extracted job skills."}
                  </p>
                </div>
              ) : null}
            </div>
            {report.matched_skills.length > matchedPreview.length ? (
              <p className="mt-3 text-xs text-muted-foreground">
                +{report.matched_skills.length - matchedPreview.length} more in Full skill evidence
              </p>
            ) : null}
          </article>

          <article className="min-w-0 rounded-xl border border-border bg-surface p-4 sm:p-5 xl:col-span-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <AlertTriangle className="h-4 w-4 text-warning" aria-hidden="true" />
                <h3 className="text-sm font-bold text-foreground">Missing or weak</h3>
              </div>
              <Badge tone={gapCount > 0 ? "warning" : "success"}>{gapCount} to review</Badge>
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              {gapPreview.map((item) => (
                <Badge
                  aria-label={`${item.skill}, ${item.label}`}
                  className="max-w-full flex-wrap gap-1 whitespace-normal [overflow-wrap:anywhere]"
                  key={`${item.label}-${item.skill}`}
                  tone={item.tone}
                >
                  <span className="min-w-0 [overflow-wrap:anywhere]">{item.skill}</span>
                  <span className="min-w-0 [overflow-wrap:anywhere]">· {item.label}</span>
                </Badge>
              ))}
              {gapCount === 0 ? (
                <div>
                  <p className="text-sm font-semibold text-foreground">
                    {hasUnclearJobRequirements ? "Gaps not available" : "No gaps detected"}
                  </p>
                  <p className="mt-1 text-sm leading-6 text-muted-foreground">
                    {hasUnclearJobRequirements
                      ? "Missing skills cannot be determined until explicit job requirements are extracted."
                      : "No missing or weak skills were found in the extracted job evidence."}
                  </p>
                </div>
              ) : null}
            </div>
            {gapCount > gapPreview.length ? (
              <p className="mt-3 text-xs text-muted-foreground">
                +{gapCount - gapPreview.length} more in Full skill evidence
              </p>
            ) : null}
          </article>

          <article className="min-w-0 rounded-xl border border-border bg-surface p-4 sm:p-5 xl:col-span-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <SearchCheck className="h-4 w-4 text-primary" aria-hidden="true" />
                <h3 className="text-sm font-bold text-foreground">ATS keywords</h3>
              </div>
              <Badge tone="neutral">{report.ats_keywords.length} reviewed</Badge>
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              {keywordPreview.map((item) => (
                <Badge
                  aria-label={`${item.keyword}, ${keywordStatusLabel(item.status)}`}
                  className="max-w-full flex-wrap gap-1 whitespace-normal [overflow-wrap:anywhere]"
                  key={item.keyword}
                  tone={keywordStatusTone(item.status)}
                >
                  <span className="min-w-0 [overflow-wrap:anywhere]">{item.keyword}</span>
                  <span className="min-w-0 [overflow-wrap:anywhere]">
                    · {keywordStatusLabel(item.status)}
                  </span>
                </Badge>
              ))}
              {keywordPreview.length === 0 ? (
                <div>
                  <p className="text-sm font-semibold text-foreground">
                    No ATS keywords extracted
                  </p>
                  <p className="mt-1 text-sm leading-6 text-muted-foreground">
                    {hasUnclearJobRequirements
                      ? "The job page did not expose enough requirement evidence for safe keyword suggestions."
                      : "No supported or add-only-if-true keywords were produced for this report."}
                  </p>
                </div>
              ) : null}
            </div>
            {report.ats_keywords.length > keywordPreview.length ? (
              <p className="mt-3 text-xs text-muted-foreground">
                +{report.ats_keywords.length - keywordPreview.length} more in Resume recommendations
              </p>
            ) : null}
          </article>

          <article className="min-w-0 rounded-xl border border-border bg-surface p-4 sm:p-5 xl:col-span-7">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <ListChecks className="h-4 w-4 text-validation" aria-hidden="true" />
                <h3 className="text-sm font-bold text-foreground">Next actions</h3>
              </div>
              <Badge tone="neutral">Top {Math.min(3, report.next_actions.length)}</Badge>
            </div>
            <ol className="mt-4 space-y-2">
              {actionPreview.map((action, index) => (
                <li className="flex gap-3 text-sm leading-6 text-muted-foreground" key={action}>
                  <span className="font-mono text-xs font-semibold text-accent">
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  {action}
                </li>
              ))}
            </ol>
            {report.next_actions.length > actionPreview.length ? (
              <p className="mt-3 text-xs text-muted-foreground">
                +{report.next_actions.length - actionPreview.length} more in Resume recommendations
              </p>
            ) : null}
          </article>
        </section>

        {report.validation_warnings.length > 0 ? (
          <section className="rounded-xl border border-warning/25 bg-warning/10 p-4 sm:p-5">
            <div className="mb-3 flex items-center gap-2">
              <CircleAlert className="h-4 w-4 text-warning" aria-hidden="true" />
              <h3 className="text-sm font-bold text-foreground">Validation warnings</h3>
            </div>
            <div className="divide-y divide-warning/20">
              {report.validation_warnings.map((warning) => (
                <article className="py-3 first:pt-0 last:pb-0" key={warning.code}>
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
                </article>
              ))}
            </div>
          </section>
        ) : null}

        <section aria-labelledby="report-details-title" className="space-y-3 pt-1">
          <div>
            <p className="font-mono text-[0.66rem] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
              Supporting detail
            </p>
            <h3 className="mt-1 text-base font-extrabold tracking-[-0.03em]" id="report-details-title">
              Expand only what you need
            </h3>
          </div>

          <ReportSectionDisclosure
            badge={
              <Badge tone={report.score_status === "provisional" ? "warning" : "neutral"}>
                {scoringVersionLabel(report)}
              </Badge>
            }
            description={scoreDetailDescription}
            icon={<SearchCheck className="h-4 w-4" aria-hidden="true" />}
            id="score-method"
            title={scoreDetailTitle}
          >
            <MatchScoreBreakdownView
              breakdown={report.score_breakdown}
              embedded
              scoringVersion={report.scoring_version}
            />
          </ReportSectionDisclosure>

          <ReportSectionDisclosure
            badge={<Badge tone="neutral">{report.matched_skills.length + gapCount} items</Badge>}
            description="Review every match, missing requirement, weak claim, and linked resume source."
            icon={<ShieldCheck className="h-4 w-4" aria-hidden="true" />}
            id="skill-evidence"
            title="Full skill evidence"
          >
            <ReportSkillEvidence
              hasUnclearJobRequirements={hasUnclearJobRequirements}
              report={report}
            />
          </ReportSectionDisclosure>

          <ReportSectionDisclosure
            badge={
              <Badge tone="neutral">
                {report.tailored_bullets.length + report.ats_keywords.length} suggestions
              </Badge>
            }
            description="See tailored bullets, the complete keyword review, and every recommended next step."
            icon={<FileCheck2 className="h-4 w-4" aria-hidden="true" />}
            id="resume-recommendations"
            title="Resume recommendations"
          >
            <ReportRecommendations
              hasUnclearJobRequirements={hasUnclearJobRequirements}
              report={report}
            />
          </ReportSectionDisclosure>

          <ReportSectionDisclosure
            badge={
              <Badge tone="neutral">
                {report.interview_questions.length} interview groups
              </Badge>
            }
            description="Copy the cover letter or open only the interview category you want to practice."
            detailsRef={materialsDisclosureRef}
            icon={<ClipboardList className="h-4 w-4" aria-hidden="true" />}
            id="application-materials"
            title="Application materials"
          >
            <div className="grid min-w-0 items-start gap-4 xl:grid-cols-2">
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
            </div>
          </ReportSectionDisclosure>
        </section>

        <WorkflowTracePanel trace={workflowTrace} />
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

function ReportMetric({ label, value }: MetricProps) {
  return (
    <div className="min-w-0 rounded-lg border border-border bg-surface p-3">
      <dt className="font-mono text-[0.62rem] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
        {label}
      </dt>
      <dd className="mt-1 font-mono text-2xl font-semibold tracking-[-0.05em] tabular-nums">
        {value}
      </dd>
    </div>
  );
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

function scoringVersionLabel(report: ApplicationReport): string {
  const version = report.score_breakdown?.scoring_version ?? report.scoring_version;
  if (version === "evidence_v2") {
    return "Evidence v2";
  }
  if (version === "deterministic_v1") {
    return "Deterministic v1";
  }
  return "Legacy score";
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

function keywordStatusLabel(
  status: ApplicationReport["ats_keywords"][number]["status"]
): string {
  if (status === "add_only_if_true") {
    return "add only if true";
  }
  return status;
}
