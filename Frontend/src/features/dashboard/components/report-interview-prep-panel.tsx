import { MessageSquareText } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import type {
  InterviewQuestionGroup,
  ResumeProfile,
  ValidationWarning
} from "@/features/dashboard/types";
import { formatEvidenceSource } from "@/features/dashboard/utils/evidence";

interface ReportInterviewPrepPanelProps {
  groups: InterviewQuestionGroup[];
  resumeProfile: ResumeProfile | null;
  warnings: ValidationWarning[];
}

export function ReportInterviewPrepPanel({
  groups,
  resumeProfile,
  warnings
}: ReportInterviewPrepPanelProps) {
  const factsById = new Map(resumeProfile?.facts.map((fact) => [fact.id, fact.text]) ?? []);

  return (
    <section className="rounded-lg border border-border bg-surface p-4" aria-labelledby="interview-prep-title">
      <div className="flex flex-wrap items-center gap-2">
        <MessageSquareText className="h-4 w-4 text-primary" aria-hidden="true" />
        <h3 className="text-sm font-semibold" id="interview-prep-title">
          Interview preparation
        </h3>
        <Badge tone={warnings.some((warning) => warning.severity === "block") ? "danger" : warnings.length > 0 ? "warning" : "success"}>
          {warnings.length > 0 ? "Needs review" : `${groups.length} group${groups.length === 1 ? "" : "s"}`}
        </Badge>
      </div>
      <p className="mt-1 text-xs leading-5 text-muted-foreground">
        Practice concise answers and use only the linked resume evidence as support.
      </p>

      {groups.length > 0 ? (
        <div className="mt-4 space-y-3">
          {groups.map((group, groupIndex) => (
            <article className="rounded-md border border-border bg-background p-3" key={`${group.category}-${groupIndex}`}>
              <h4 className="text-sm font-semibold text-foreground">{group.category}</h4>
              <ol className="mt-2 list-decimal space-y-2 pl-5 text-sm leading-6 text-muted-foreground">
                {group.questions.map((question) => (
                  <li key={question}>{question}</li>
                ))}
              </ol>

              {group.suggested_answer_evidence_ids.length > 0 ? (
                <details className="group mt-3 rounded-md border border-border bg-surface">
                  <summary className="cursor-pointer list-none px-3 py-2 text-xs font-semibold text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/35">
                    Suggested answer evidence ({group.suggested_answer_evidence_ids.length})
                  </summary>
                  <div className="space-y-2 border-t border-border p-3">
                    {group.suggested_answer_evidence_ids.map((evidenceId) => {
                      const evidence = formatEvidenceSource(evidenceId);
                      return (
                        <div key={`${group.category}-${evidenceId}`}>
                          <Badge tone={evidence.tone}>{evidence.label}</Badge>
                          <p className="mt-1 text-xs leading-5 text-muted-foreground">
                            {factsById.get(evidenceId) ??
                              "Evidence text is unavailable in this saved view."}
                          </p>
                        </div>
                      );
                    })}
                  </div>
                </details>
              ) : null}
            </article>
          ))}
        </div>
      ) : (
        <div className="mt-4 rounded-md border border-dashed border-border bg-background p-4 text-sm text-muted-foreground">
          No interview questions were generated for this report.
        </div>
      )}

      {warnings.length > 0 ? (
        <ul className="mt-3 space-y-2" aria-label="Interview preparation validation issues">
          {warnings.map((warning) => (
            <li className="rounded-md border border-warning/25 bg-warning/10 p-3 text-xs leading-5 text-muted-foreground" key={warning.code}>
              {warning.message}
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
