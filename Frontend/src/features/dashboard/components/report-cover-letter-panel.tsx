import { Check, ChevronDown, ClipboardCopy, FileText, ShieldCheck } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type {
  ResumeProfile,
  ValidationStatus,
  ValidationWarning
} from "@/features/dashboard/types";
import { formatEvidenceSource } from "@/features/dashboard/utils/evidence";

interface ReportCoverLetterPanelProps {
  coverLetter: string;
  evidenceIds: string[];
  resumeProfile: ResumeProfile | null;
  warnings: ValidationWarning[];
}

export function ReportCoverLetterPanel({
  coverLetter,
  evidenceIds,
  resumeProfile,
  warnings
}: ReportCoverLetterPanelProps) {
  const [copyState, setCopyState] = useState<"idle" | "copied" | "failed">("idle");
  const status = validationStatus(warnings);
  const factsById = new Map(resumeProfile?.facts.map((fact) => [fact.id, fact.text]) ?? []);

  async function copyCoverLetter() {
    try {
      await navigator.clipboard.writeText(coverLetter);
      setCopyState("copied");
    } catch {
      setCopyState("failed");
    }
  }

  return (
    <section
      aria-labelledby="cover-letter-title"
      className="min-w-0 rounded-lg border border-border bg-surface p-4"
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <FileText className="h-4 w-4 text-primary" aria-hidden="true" />
            <h3 className="text-sm font-semibold" id="cover-letter-title">
              Cover letter draft
            </h3>
            <Badge tone={validationTone(status)}>{validationLabel(status)}</Badge>
          </div>
          <p className="mt-1 text-xs leading-5 text-muted-foreground">
            Review and personalize this evidence-backed draft before sending it.
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <span aria-live="polite" className="text-xs text-muted-foreground">
            {copyState === "copied"
              ? "Copied"
              : copyState === "failed"
                ? "Copy failed"
                : ""}
          </span>
          <Button
            className="h-9 px-3 text-xs"
            icon={
              copyState === "copied" ? (
                <Check className="h-3.5 w-3.5" aria-hidden="true" />
              ) : (
                <ClipboardCopy className="h-3.5 w-3.5" aria-hidden="true" />
              )
            }
            onClick={() => void copyCoverLetter()}
            variant="secondary"
          >
            Copy draft
          </Button>
        </div>
      </div>

      <details
        className="group mt-4 overflow-hidden rounded-md border border-border bg-background"
        data-testid="cover-letter-draft-disclosure"
      >
        <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-3 py-2.5 text-xs font-semibold text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-primary">
          <span>Read full cover letter</span>
          <span className="flex shrink-0 items-center gap-2 text-muted-foreground">
            {coverLetter.length.toLocaleString()} characters
            <ChevronDown
              aria-hidden="true"
              className="h-4 w-4 transition-transform group-open:rotate-180"
            />
          </span>
        </summary>
        <div className="whitespace-pre-line break-words border-t border-border p-4 text-sm leading-7 text-foreground [overflow-wrap:anywhere]">
          {coverLetter}
        </div>
      </details>

      {evidenceIds.length > 0 ? (
        <details className="group mt-3 rounded-md border border-border bg-background">
          <summary className="cursor-pointer list-none px-3 py-2 text-xs font-semibold text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/35">
            Supporting resume evidence ({evidenceIds.length})
          </summary>
          <div className="space-y-2 border-t border-border p-3">
            {evidenceIds.map((evidenceId) => {
              const evidence = formatEvidenceSource(evidenceId);
              return (
                <div className="rounded border border-border bg-surface p-2" key={evidenceId}>
                  <Badge tone={evidence.tone}>{evidence.label}</Badge>
                  <p className="mt-2 text-xs leading-5 text-muted-foreground [overflow-wrap:anywhere]">
                    {factsById.get(evidenceId) ?? "Evidence text is unavailable in this saved view."}
                  </p>
                </div>
              );
            })}
          </div>
        </details>
      ) : (
        <div className="mt-3 flex items-start gap-2 rounded-md border border-warning/25 bg-warning/10 p-3">
          <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-warning" aria-hidden="true" />
          <p className="text-xs leading-5 text-muted-foreground">
            This saved report does not include cover-letter evidence references. Verify every claim
            against the resume before using the draft.
          </p>
        </div>
      )}

      {warnings.length > 0 ? (
        <ul className="mt-3 space-y-2" aria-label="Cover letter validation issues">
          {warnings.map((warning) => (
            <li className="rounded-md border border-warning/25 bg-warning/10 p-3" key={warning.code}>
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone={warning.severity === "block" ? "danger" : "warning"}>
                  {warning.severity === "block" ? "Blocked" : "Review"}
                </Badge>
                <span className="min-w-0 text-xs font-medium text-foreground [overflow-wrap:anywhere]">
                  {warning.message}
                </span>
              </div>
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}

function validationStatus(warnings: ValidationWarning[]): ValidationStatus {
  if (warnings.some((warning) => warning.severity === "block")) {
    return "block";
  }
  return warnings.length > 0 ? "warn" : "pass";
}

function validationTone(status: ValidationStatus): "success" | "warning" | "danger" {
  if (status === "block") {
    return "danger";
  }
  return status === "warn" ? "warning" : "success";
}

function validationLabel(status: ValidationStatus): string {
  if (status === "block") {
    return "Blocked";
  }
  return status === "warn" ? "Needs review" : "Validated draft";
}
