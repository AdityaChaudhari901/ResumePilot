import {
  Bot,
  FileSearch,
  GitBranch,
  Loader2,
  Play,
  SearchCheck,
  ShieldCheck
} from "lucide-react";
import type { FormEvent } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Panel } from "@/components/ui/panel";
import { WorkflowApprovalPanel } from "@/features/dashboard/components/workflow-approval-panel";
import type {
  UsageSummaryResponse,
  WorkflowApprovalDecision,
  WorkflowOperation
} from "@/features/dashboard/types";

interface AiWorkflowCardProps {
  allowLiveAiProcessing: boolean;
  canAnalyze: boolean;
  isAnalyzing: boolean;
  isSubmittingApproval: boolean;
  operation: WorkflowOperation | null;
  usage: UsageSummaryResponse | null;
  onAllowLiveAiProcessingChange: (enabled: boolean) => void;
  onApprovalDecision: (decision: WorkflowApprovalDecision) => void;
  onCancel: () => void;
  onResume: () => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}

const WORKFLOW_ITEMS = [
  {
    description: "Fetch and normalize the public job listing into structured requirements.",
    icon: FileSearch,
    label: "Parse job evidence"
  },
  {
    description: "Compare role requirements against parsed resume facts and evidence IDs.",
    icon: SearchCheck,
    label: "Match resume evidence"
  },
  {
    description: "Draft ATS keywords, resume bullets, cover letter, and interview prep with LangGraph.",
    icon: Bot,
    label: "Generate application assets"
  },
  {
    description: "Reject unsupported claims before the report is shown or exported.",
    icon: ShieldCheck,
    label: "Validate output"
  }
];

export function AiWorkflowCard({
  allowLiveAiProcessing,
  canAnalyze,
  isAnalyzing,
  isSubmittingApproval,
  onCancel,
  onAllowLiveAiProcessingChange,
  onApprovalDecision,
  onResume,
  onSubmit,
  operation,
  usage
}: AiWorkflowCardProps) {
  const pendingApproval =
    operation?.status === "waiting_for_approval" ? operation.approval : null;
  const isOperationActive = Boolean(
    operation && !["succeeded", "canceled", "failed", "dead_lettered"].includes(operation.status)
  );
  const shouldShowProgress = Boolean(operation && isOperationActive && !pendingApproval);
  const workflowMode = pendingApproval
    ? "Approval required"
    : usage?.live_ai_enabled
      ? "Live AI eligible"
      : "Deterministic gate";
  const workflowModeTone = pendingApproval
    ? "warning"
    : usage?.live_ai_enabled
      ? "primary"
      : "neutral";

  return (
    <Panel
      action={<Badge tone={workflowModeTone}>{workflowMode}</Badge>}
      eyebrow="Step 04"
      title="AI services"
    >
      <form className="space-y-5" onSubmit={onSubmit}>
        <div className="border-l-2 border-primary bg-surface px-4 py-3">
          <div className="flex items-start gap-3">
            <GitBranch className="mt-0.5 h-5 w-5 text-primary" aria-hidden="true" />
            <div>
              <p className="text-sm font-semibold text-foreground">
                ResumePilot now has both inputs.
              </p>
              <p className="mt-1 text-sm leading-6 text-muted-foreground">
                Run the evidence-first workflow to produce the validated job-fit report and export
                ready application material.
              </p>
            </div>
          </div>
        </div>

        <ol className="grid gap-px overflow-hidden rounded-2xl border border-border bg-border md:grid-cols-2">
          {WORKFLOW_ITEMS.map((item, index) => {
            const Icon = item.icon;

            return (
              <li className="bg-surface-raised p-4" key={item.label}>
                <div className="flex items-start gap-3">
                  <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary font-mono text-xs font-semibold text-primary-foreground">
                    0{index + 1}
                  </span>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <Icon className="h-4 w-4 text-primary" aria-hidden="true" />
                      <p className="text-sm font-semibold text-foreground">{item.label}</p>
                    </div>
                    <p className="mt-1 text-xs leading-5 text-muted-foreground">
                      {item.description}
                    </p>
                  </div>
                </div>
              </li>
            );
          })}
        </ol>

        {usage?.live_ai_enabled ? (
          <label className="flex items-start gap-3 rounded-xl border border-border-strong bg-surface p-4 text-sm">
            <input
              checked={allowLiveAiProcessing}
              className="mt-1 h-4 w-4"
              disabled={isAnalyzing || isSubmittingApproval || Boolean(pendingApproval)}
              onChange={(event) => onAllowLiveAiProcessingChange(event.target.checked)}
              type="checkbox"
            />
            <span>
              <span className="block font-semibold text-foreground">
                Allow live AI processing for this analysis
              </span>
              <span className="mt-1 block leading-5 text-muted-foreground">
                Sends job content and evidence facts to the configured provider. Resume name,
                email, phone, links, and the deterministic cover letter are excluded.
              </span>
            </span>
          </label>
        ) : null}

        {shouldShowProgress && operation ? (
          <div
            aria-live="polite"
            className="rounded-xl border border-primary/40 bg-primary/10 p-4"
          >
            <div className="flex items-center justify-between gap-3 text-sm">
              <span className="font-semibold text-foreground">
                {operationStageLabel(operation.stage)}
              </span>
              <span className="font-mono text-xs text-muted-foreground">
                {operation.progress_percent}%
              </span>
            </div>
            <progress
              aria-label="Analysis progress"
              className="mt-2 h-2 w-full accent-primary"
              max={100}
              value={operation.progress_percent}
            />
            <p className="mt-2 text-xs text-muted-foreground">
              Attempt {operation.attempt_count} of {operation.max_attempts}. This work is durable;
              refreshing the page will not duplicate the analysis.
            </p>
          </div>
        ) : null}

        {pendingApproval ? (
          <WorkflowApprovalPanel
            approval={pendingApproval}
            isSubmitting={isSubmittingApproval}
            onDecision={onApprovalDecision}
          />
        ) : null}

        <div className="flex flex-col gap-3 border-t border-border pt-4 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-xs leading-5 text-muted-foreground">
            Live processing uses LangGraph and pauses before a live draft can replace the
            deterministic report. Without consent, ResumePilot keeps the deterministic evidence
            workflow.
          </p>
          <div className="flex gap-2">
            {operation?.cancelable ? (
              <Button onClick={onCancel} type="button" variant="secondary">
                Cancel
              </Button>
            ) : null}
            {isOperationActive && !isAnalyzing && !isSubmittingApproval && !pendingApproval ? (
              <Button onClick={onResume} type="button" variant="secondary">
                Resume status
              </Button>
            ) : null}
            <Button
              disabled={!canAnalyze}
              icon={
                isAnalyzing || isSubmittingApproval ? (
                  <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                ) : (
                  <Play className="h-4 w-4" aria-hidden="true" />
                )
              }
              type="submit"
            >
              Run AI analysis
            </Button>
          </div>
        </div>
      </form>
    </Panel>
  );
}

function operationStageLabel(stage: string): string {
  const labels: Record<string, string> = {
    approval_required: "Your approval is required",
    awaiting_approval: "Your approval is required",
    cancel_requested: "Canceling analysis",
    fetching_job: "Loading reviewed job evidence",
    generating_report: "Generating application materials",
    matching_evidence: "Matching résumé evidence",
    parsing_job: "Parsing job requirements",
    queued: "Analysis queued",
    retry_scheduled: "Retry scheduled",
    saving_application: "Saving application workspace",
    starting: "Starting analysis",
    validating_claims: "Validating every claim",
    waiting_for_approval: "Your approval is required"
  };
  return labels[stage] ?? "Analysis in progress";
}
