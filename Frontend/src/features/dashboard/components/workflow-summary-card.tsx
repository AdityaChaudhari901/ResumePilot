import { Bot, BriefcaseBusiness, ClipboardList, FileCheck2, FileText } from "lucide-react";
import type { ReactNode } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Panel } from "@/components/ui/panel";
import type {
  AgentWorkflowTrace,
  JobAnalysisResponse,
  JobPreviewResponse,
  JobSourceType,
  ResumeUploadResponse,
  TailoredResumeDraft,
  WorkflowOperation
} from "@/features/dashboard/types";

interface WorkflowSummaryCardProps {
  activeOperation: WorkflowOperation | null;
  analysis: JobAnalysisResponse | null;
  isJobEvidenceReady: boolean;
  isJobReady: boolean;
  isResumeReady: boolean;
  jobPreview: JobPreviewResponse | null;
  jobSourceType: JobSourceType;
  jobText: string;
  jobUrl: string;
  resume: ResumeUploadResponse | null;
  tailoredResumeDraft: TailoredResumeDraft | null;
  workflowTrace: AgentWorkflowTrace | null;
  onEditJob: () => void;
  onEditResume: () => void;
  onReviewJob: () => void;
  onRunAi: () => void;
  onViewDraft: () => void;
  onViewReport: () => void;
}

export function WorkflowSummaryCard({
  activeOperation,
  analysis,
  isJobEvidenceReady,
  isJobReady,
  isResumeReady,
  jobPreview,
  jobSourceType,
  jobText,
  jobUrl,
  onEditJob,
  onEditResume,
  onReviewJob,
  onRunAi,
  onViewDraft,
  onViewReport,
  resume,
  tailoredResumeDraft,
  workflowTrace
}: WorkflowSummaryCardProps) {
  const resumeDetail = getResumeDetail(resume, isJobEvidenceReady);
  const isApprovalPending = activeOperation?.status === "waiting_for_approval";
  const isOperationActive = Boolean(
    activeOperation &&
      !["succeeded", "canceled", "failed", "dead_lettered"].includes(activeOperation.status)
  );

  return (
    <Panel as="aside" eyebrow="Current application" title="Workflow summary">
      <div className="grid min-w-0 w-full gap-px overflow-hidden rounded-xl border border-border bg-border">
        <SummaryRow
          actionLabel="Edit"
          actionName="Edit job listing"
          detail={formatJobDetail(jobSourceType, jobUrl, jobText)}
          icon={<BriefcaseBusiness className="h-4 w-4 text-primary" aria-hidden="true" />}
          isActionDisabled={isOperationActive}
          label="Job listing"
          status={isJobReady ? "ready" : "pending"}
          statusLabel={
            isJobReady ? (jobSourceType === "url" ? "URL added" : "Text added") : "Needed first"
          }
          onAction={onEditJob}
        />
        <SummaryRow
          actionLabel={isJobEvidenceReady ? "Review" : "Open"}
          actionName="Review extracted job evidence"
          detail={formatJobEvidenceDetail(jobPreview)}
          icon={<BriefcaseBusiness className="h-4 w-4 text-primary" aria-hidden="true" />}
          isActionDisabled={!isJobReady || isOperationActive}
          label="Job evidence"
          status={isJobEvidenceReady ? "ready" : "pending"}
          statusLabel={isJobEvidenceReady ? "Reviewed" : "Pending"}
          onAction={onReviewJob}
        />
        <SummaryRow
          actionLabel={isResumeReady ? "Review" : "Upload"}
          actionName={isResumeReady ? "Review resume evidence step" : "Open resume evidence step"}
          detail={resumeDetail}
          icon={<FileText className="h-4 w-4 text-primary" aria-hidden="true" />}
          isActionDisabled={!isJobEvidenceReady || isOperationActive}
          label="Resume evidence"
          status={isResumeReady ? "ready" : "pending"}
          statusLabel={isResumeReady ? "Parsed" : "Pending"}
          onAction={onEditResume}
        />
        <SummaryRow
          actionLabel={isApprovalPending ? "Review" : analysis ? "Rerun" : "Run"}
          actionName={
            isApprovalPending
              ? "Review the live AI draft approval"
              : analysis
                ? "Open AI services to rerun"
                : "Open AI services step"
          }
          detail={
            isApprovalPending
              ? activeOperation.approval?.title ?? "Live AI draft needs your decision"
              : workflowTrace
                ? workflowModeLabel(workflowTrace.mode)
                : "Evidence workflow not run"
          }
          icon={<Bot className="h-4 w-4 text-primary" aria-hidden="true" />}
          isActionDisabled={!isJobEvidenceReady || !isResumeReady}
          label="AI services"
          status={isApprovalPending ? "attention" : analysis ? "ready" : "pending"}
          statusLabel={isApprovalPending ? "Approval required" : analysis ? "Complete" : "Ready after resume"}
          onAction={onRunAi}
        />
        <SummaryRow
          actionLabel="View"
          actionName="View report"
          detail={analysis ? `Report ${analysis.report_id}` : "No validated report yet"}
          icon={<ClipboardList className="h-4 w-4 text-primary" aria-hidden="true" />}
          isActionDisabled={!analysis || isOperationActive}
          label="Validated report"
          status={analysis ? "ready" : "pending"}
          statusLabel={analysis ? "Generated" : "Pending"}
          onAction={onViewReport}
        />
        <SummaryRow
          actionLabel="Open"
          actionName="Open tailored resume draft"
          detail={formatDraftDetail(tailoredResumeDraft, analysis)}
          icon={<FileCheck2 className="h-4 w-4 text-primary" aria-hidden="true" />}
          isActionDisabled={!analysis || isOperationActive}
          label="Tailored resume"
          status={tailoredResumeDraft?.export_ready ? "ready" : "pending"}
          statusLabel={tailoredResumeDraft?.export_ready ? "Export ready" : "Needs review"}
          onAction={onViewDraft}
        />
      </div>
      <p className="mt-4 border-l-2 border-primary bg-surface px-3 py-2.5 text-xs leading-5 text-muted-foreground">
        Inputs are reviewed first. Exports should use accepted draft bullets, not unreviewed
        suggestions.
      </p>
    </Panel>
  );
}

interface SummaryRowProps {
  actionLabel: string;
  actionName: string;
  detail: string;
  icon: ReactNode;
  isActionDisabled: boolean;
  label: string;
  status: "attention" | "pending" | "ready";
  statusLabel: string;
  onAction: () => void;
}

function SummaryRow({
  actionLabel,
  actionName,
  detail,
  icon,
  isActionDisabled,
  label,
  onAction,
  status,
  statusLabel
}: SummaryRowProps) {
  return (
    <div className="min-w-0 bg-surface-raised p-4">
      <div className="flex min-w-0 flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            {icon}
            <p className="truncate text-sm font-semibold text-foreground">{label}</p>
          </div>
          <p className="mt-1 truncate text-xs text-muted-foreground">{detail}</p>
        </div>
        <Badge
          className="self-start shrink-0"
          tone={status === "ready" ? "success" : status === "attention" ? "warning" : "neutral"}
        >
          {statusLabel}
        </Badge>
      </div>
      <div className="mt-3 flex justify-end">
        <Button
          aria-label={actionName}
          className="h-8 px-3 text-xs"
          disabled={isActionDisabled}
          onClick={onAction}
          variant="secondary"
        >
          {actionLabel}
        </Button>
      </div>
    </div>
  );
}

function formatJobDetail(jobSourceType: JobSourceType, jobUrl: string, jobText: string): string {
  if (jobSourceType === "pasted_text") {
    return jobText.trim()
      ? `Pasted description · ${jobText.trim().length.toLocaleString()} characters`
      : "No pasted job description yet";
  }
  if (!jobUrl.trim()) {
    return "No job listing URL yet";
  }

  try {
    const parsedUrl = new URL(jobUrl);
    return parsedUrl.hostname;
  } catch {
    return jobUrl;
  }
}

function getResumeDetail(
  resume: ResumeUploadResponse | null,
  isJobEvidenceReady: boolean
): string {
  if (resume) {
    return resume.candidate_name || `Resume ID ${resume.resume_id}`;
  }
  return isJobEvidenceReady ? "No resume uploaded yet" : "Waiting for reviewed job evidence";
}

function formatJobEvidenceDetail(preview: JobPreviewResponse | null): string {
  if (!preview) {
    return "Waiting for job extraction";
  }
  const role = preview.profile.role_title ?? "Unknown role";
  const company = preview.profile.company ?? "Unknown company";
  return `${role} · ${company}`;
}

function workflowModeLabel(mode: AgentWorkflowTrace["mode"]): string {
  return mode === "deterministic_fallback"
    ? "Deterministic fallback completed"
    : "Live AI workflow completed";
}

function formatDraftDetail(
  draft: TailoredResumeDraft | null,
  analysis: JobAnalysisResponse | null
): string {
  if (!analysis) {
    return "No report generated yet";
  }
  if (!draft) {
    return "Draft loading after report";
  }
  return `${draft.accepted_count} accepted · ${draft.pending_count} pending`;
}
