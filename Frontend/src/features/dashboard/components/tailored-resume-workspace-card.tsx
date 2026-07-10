import {
  CheckCircle2,
  CircleAlert,
  CircleDashed,
  FileCode2,
  FileDown,
  FileText,
  RefreshCcw,
  Save,
  ShieldCheck,
  Undo2,
  XCircle
} from "lucide-react";
import { type ReactNode, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Panel } from "@/components/ui/panel";
import { cn } from "@/lib/cn";
import type {
  TailoredResumeDraft,
  TailoredResumeExportFormat,
  TailoredResumeItem,
  TailoredResumeItemStatus,
  TailoredResumeItemUpdate
} from "@/features/dashboard/types";
import type { ApiProblem } from "@/features/dashboard/utils/api-error";

interface TailoredResumeWorkspaceCardProps {
  applicationId: number | null;
  draft: TailoredResumeDraft | null;
  isExporting: TailoredResumeExportFormat | null;
  isLoading: boolean;
  isUpdating: boolean;
  onExport: (format: TailoredResumeExportFormat) => Promise<void>;
  onRefresh: () => void;
  onUpdateItem: (itemId: string, update: TailoredResumeItemUpdate) => Promise<ApiProblem | null>;
  onViewReport: () => void;
}

export function TailoredResumeWorkspaceCard({
  applicationId,
  draft,
  isExporting,
  isLoading,
  isUpdating,
  onExport,
  onRefresh,
  onUpdateItem,
  onViewReport
}: TailoredResumeWorkspaceCardProps) {
  const canExport = Boolean(applicationId && draft?.export_ready);

  return (
    <Panel
      action={
        <div className="flex flex-wrap justify-end gap-2">
          <Button
            icon={<RefreshCcw className="h-4 w-4" aria-hidden="true" />}
            onClick={onRefresh}
            variant="secondary"
          >
            Refresh
          </Button>
          <Button onClick={onViewReport} variant="secondary">
            View report
          </Button>
        </div>
      }
      eyebrow="Step 06"
      title="Tailored resume workspace"
    >
      <div className="space-y-5">
        <div className="grid gap-3 md:grid-cols-4">
          <DraftMetric label="Accepted" value={draft?.accepted_count ?? 0} />
          <DraftMetric label="Pending" value={draft?.pending_count ?? 0} />
          <DraftMetric label="Rejected" value={draft?.rejected_count ?? 0} />
          <DraftMetric label="Status" value={draftStatusLabel(draft?.status)} />
        </div>

        {isLoading ? (
          <div className="rounded-md border border-border bg-surface p-4 text-sm text-muted-foreground">
            Loading tailored resume draft...
          </div>
        ) : null}

        {!isLoading && !applicationId ? (
          <EmptyDraftState title="No application selected">
            Open an analyzed application from the pipeline to review tailored resume bullets.
          </EmptyDraftState>
        ) : null}

        {!isLoading && draft && draft.items.length === 0 ? (
          <EmptyDraftState title="No exportable suggestions yet">
            ResumePilot did not find project or work evidence strong enough for tailored bullets.
            Add truthful project evidence, rerun analysis, then return to this workspace.
          </EmptyDraftState>
        ) : null}

        {draft?.items.length ? (
          <section className="space-y-3" aria-label="Tailored bullet review items">
            {draft.items.map((item) => (
              <TailoredResumeItemRow
                isUpdating={isUpdating}
                item={item}
                key={`${item.id}:${item.edited_bullet ?? item.suggested_bullet}`}
                onUpdateItem={onUpdateItem}
              />
            ))}
          </section>
        ) : null}

        <section
          className={cn(
            "rounded-lg border p-4",
            canExport ? "border-primary/25 bg-primary/10" : "border-border bg-surface"
          )}
          aria-label="Reviewed resume export"
        >
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <ShieldCheck
                  className={cn(
                    "h-4 w-4",
                    canExport ? "text-primary" : "text-muted-foreground"
                  )}
                  aria-hidden="true"
                />
                <h3 className="text-sm font-semibold text-foreground">Reviewed export</h3>
              </div>
              <p className="mt-1 text-sm leading-6 text-muted-foreground">
                {canExport
                  ? "Exports include accepted bullets only. Rejected and pending suggestions stay out of the resume."
                  : "Accept at least one evidence-backed bullet before exporting the tailored resume."}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              {canExport ? (
                <>
                  <ExportButton
                    icon={<FileText className="h-4 w-4" aria-hidden="true" />}
                    isExporting={isExporting === "docx"}
                    isUnavailable={Boolean(isExporting) || isUpdating}
                    label="DOCX"
                    onClick={() => void onExport("docx")}
                    variant="secondary"
                  >
                    DOCX
                  </ExportButton>
                  <ExportButton
                    icon={<FileCode2 className="h-4 w-4" aria-hidden="true" />}
                    isExporting={isExporting === "latex"}
                    isUnavailable={Boolean(isExporting) || isUpdating}
                    label="LaTeX"
                    onClick={() => void onExport("latex")}
                    variant="secondary"
                  >
                    LaTeX
                  </ExportButton>
                  <ExportButton
                    icon={<FileDown className="h-4 w-4" aria-hidden="true" />}
                    isExporting={isExporting === "pdf"}
                    isUnavailable={Boolean(isExporting) || isUpdating}
                    label="PDF"
                    onClick={() => void onExport("pdf")}
                    variant="primary"
                  >
                    PDF
                  </ExportButton>
                </>
              ) : (
                <Badge tone="neutral">Export locked</Badge>
              )}
            </div>
          </div>
        </section>
      </div>
    </Panel>
  );
}

function ExportButton({
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

function TailoredResumeItemRow({
  isUpdating,
  item,
  onUpdateItem
}: {
  isUpdating: boolean;
  item: TailoredResumeItem;
  onUpdateItem: (itemId: string, update: TailoredResumeItemUpdate) => Promise<ApiProblem | null>;
}) {
  const [draftText, setDraftText] = useState(item.edited_bullet ?? item.suggested_bullet);
  const [problem, setProblem] = useState<ApiProblem | null>(null);

  const statusIcon = itemStatusIcon(item.status);
  const StatusIcon = statusIcon.icon;
  const hasValidationWarnings = item.validation_warnings.length > 0;
  const hasChanged = draftText.trim() !== (item.edited_bullet ?? item.suggested_bullet);

  async function update(status?: TailoredResumeItemStatus) {
    const nextProblem = await onUpdateItem(item.id, {
      edited_bullet: draftText.trim(),
      ...(status ? { status } : {})
    });
    setProblem(nextProblem);
  }

  async function reset() {
    const nextProblem = await onUpdateItem(item.id, {
      reset_edited_bullet: true,
      status: "pending"
    });
    setProblem(nextProblem);
  }

  return (
    <article className="rounded-lg border border-border bg-surface p-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <StatusIcon className={cn("h-4 w-4", statusIcon.className)} aria-hidden="true" />
            <h3 className="text-sm font-semibold text-foreground">Evidence-backed bullet</h3>
            <Badge tone={itemStatusTone(item.status)}>{itemStatusLabel(item.status)}</Badge>
            {hasValidationWarnings ? <Badge tone="warning">needs review</Badge> : null}
          </div>
        </div>
        <div className="flex shrink-0 flex-wrap gap-2">
          <Button
            className="h-8 px-3 text-xs"
            disabled={isUpdating || !hasChanged}
            icon={<Save className="h-3.5 w-3.5" aria-hidden="true" />}
            onClick={() => void update()}
            variant="secondary"
          >
            Save
          </Button>
          <Button
            className="h-8 px-3 text-xs"
            disabled={isUpdating}
            icon={<CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" />}
            onClick={() => void update("accepted")}
            variant="secondary"
          >
            Accept
          </Button>
          <Button
            className="h-8 px-3 text-xs"
            disabled={isUpdating}
            icon={<XCircle className="h-3.5 w-3.5" aria-hidden="true" />}
            onClick={() => void update("rejected")}
            variant="secondary"
          >
            Reject
          </Button>
          {item.status !== "pending" ? (
            <Button
              className="h-8 px-3 text-xs"
              disabled={isUpdating}
              icon={<Undo2 className="h-3.5 w-3.5" aria-hidden="true" />}
              onClick={() => void reset()}
              variant="ghost"
            >
              Reset edit
            </Button>
          ) : null}
        </div>
      </div>

      <div className="mt-4 grid gap-3 lg:grid-cols-2" aria-label="Original and proposed bullet comparison">
        <section className="rounded-md border border-border bg-background p-3">
          <p className="text-xs font-semibold uppercase tracking-normal text-muted-foreground">
            Original resume evidence
          </p>
          <p className="mt-2 text-sm leading-6 text-foreground">{item.source_bullet}</p>
        </section>

        <label className="block rounded-md border border-primary/20 bg-primary/5 p-3">
          <span className="block text-xs font-semibold uppercase tracking-normal text-muted-foreground">
            Proposed / edited bullet
          </span>
          <textarea
            aria-label={`Edit tailored bullet ${item.id}`}
            className="mt-2 min-h-32 w-full resize-y rounded-md border border-border bg-surface-inset px-3 py-2 text-sm leading-6 text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/35"
            disabled={isUpdating}
            onChange={(event) => {
              setDraftText(event.target.value);
              setProblem(null);
            }}
            value={draftText}
          />
        </label>
      </div>

      <section className="mt-3 rounded-md border border-border bg-background p-3" aria-label="Why this bullet changed">
        <p className="text-xs font-semibold uppercase tracking-normal text-muted-foreground">
          Why this change
        </p>
        <div className="mt-2 flex flex-wrap gap-2">
          {item.evidence_labels.map((label, index) => (
            <Badge key={`${item.id}-${label}-${index}`} tone="success">
              {label}
            </Badge>
          ))}
          {item.jd_keywords_used.map((keyword) => (
            <Badge key={`${item.id}-${keyword}`} tone="primary">
              JD keyword: {keyword}
            </Badge>
          ))}
          {item.evidence_labels.length === 0 && item.jd_keywords_used.length === 0 ? (
            <span className="text-xs text-muted-foreground">
              No additional keyword or evidence labels were attached.
            </span>
          ) : null}
        </div>
      </section>

      {item.evidence_texts.length > 0 ? (
        <details className="group mt-3 rounded-md border border-border bg-background">
          <summary className="cursor-pointer list-none px-3 py-2 text-xs font-semibold text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/35">
            Linked resume evidence
          </summary>
          <div className="space-y-2 border-t border-border p-3">
            {item.evidence_texts.map((text, index) => (
              <p className="text-xs leading-5 text-muted-foreground" key={`${item.id}-${index}`}>
                {text}
              </p>
            ))}
          </div>
        </details>
      ) : null}

      {item.validation_warnings.length > 0 ? (
        <div className="mt-3 space-y-2">
          {item.validation_warnings.map((warning) => (
            <div
              className="rounded-md border border-warning/25 bg-warning/10 p-3"
              key={`${item.id}-${warning.code}`}
            >
              <div className="flex items-center gap-2">
                <CircleAlert className="h-4 w-4 text-warning" aria-hidden="true" />
                <Badge tone={warning.severity === "block" ? "danger" : "warning"}>
                  {warning.severity === "block" ? "Blocked" : "Needs review"}
                </Badge>
              </div>
              <p className="mt-1 text-xs leading-5 text-muted-foreground">{warning.message}</p>
              <p className="mt-1 font-mono text-xs text-muted-foreground">{warning.code}</p>
            </div>
          ))}
        </div>
      ) : null}

      {problem ? <InlineApiProblem itemId={item.id} problem={problem} /> : null}
    </article>
  );
}

function InlineApiProblem({ itemId, problem }: { itemId: string; problem: ApiProblem }) {
  return (
    <div
      aria-live="assertive"
      className="mt-3 rounded-md border border-destructive/25 bg-destructive/10 p-3"
      role="alert"
    >
      <div className="flex items-start gap-2">
        <CircleAlert className="mt-0.5 h-4 w-4 shrink-0 text-destructive" aria-hidden="true" />
        <div className="min-w-0">
          <p className="text-sm font-semibold text-foreground">Change blocked</p>
          <p className="mt-1 text-xs leading-5 text-muted-foreground">{problem.message}</p>
        </div>
      </div>

      {problem.warnings.length > 0 ? (
        <ul className="mt-3 space-y-2">
          {problem.warnings.map((warning) => (
            <li
              className="rounded border border-destructive/20 bg-background p-2 text-xs leading-5 text-foreground"
              key={`${itemId}-${warning.code}`}
            >
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone={warning.severity === "block" ? "danger" : "warning"}>
                  {warning.severity === "block" ? "Blocked" : "Review"}
                </Badge>
                <span>{warning.message}</span>
              </div>
              <p className="mt-1 font-mono text-xs text-muted-foreground">
                {warning.code}
              </p>
            </li>
          ))}
        </ul>
      ) : null}

      {problem.fieldErrors.length > 0 ? (
        <ul className="mt-3 list-disc space-y-1 pl-5 text-xs text-muted-foreground">
          {problem.fieldErrors.map((error) => (
            <li key={`${itemId}-${error.field}-${error.message}`}>
              {error.field}: {error.message}
            </li>
          ))}
        </ul>
      ) : null}

      {problem.retryAfter !== undefined ? (
        <p className="mt-2 text-xs text-muted-foreground">
          Retry after {problem.retryAfter} second{problem.retryAfter === 1 ? "" : "s"}.
        </p>
      ) : null}
    </div>
  );
}

function DraftMetric({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="rounded-md border border-border bg-surface p-3">
      <p className="text-xs font-semibold uppercase tracking-normal text-muted-foreground">{label}</p>
      <p className="mt-2 font-mono text-2xl font-semibold tabular-nums text-foreground">
        {value}
      </p>
    </div>
  );
}

function EmptyDraftState({ children, title }: { children: string; title: string }) {
  return (
    <div className="rounded-md border border-border bg-surface p-4">
      <p className="text-sm font-semibold text-foreground">{title}</p>
      <p className="mt-1 text-sm leading-6 text-muted-foreground">{children}</p>
    </div>
  );
}

function itemStatusIcon(status: TailoredResumeItemStatus) {
  if (status === "accepted") {
    return { className: "text-validation", icon: CheckCircle2 };
  }
  if (status === "rejected") {
    return { className: "text-destructive", icon: XCircle };
  }
  return { className: "text-muted-foreground", icon: CircleDashed };
}

function itemStatusLabel(status: TailoredResumeItemStatus): string {
  const labels: Record<TailoredResumeItemStatus, string> = {
    accepted: "Accepted",
    pending: "Pending",
    rejected: "Rejected"
  };
  return labels[status];
}

function itemStatusTone(status: TailoredResumeItemStatus): "success" | "warning" | "neutral" {
  if (status === "accepted") {
    return "success";
  }
  if (status === "rejected") {
    return "warning";
  }
  return "neutral";
}

function draftStatusLabel(status: TailoredResumeDraft["status"] | undefined): string {
  if (!status) {
    return "Not ready";
  }
  const labels: Record<TailoredResumeDraft["status"], string> = {
    draft: "Draft",
    exported: "Exported",
    reviewed: "Reviewed"
  };
  return labels[status];
}
