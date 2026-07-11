import { AlertTriangle, CheckCircle2, ChevronDown } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { EvidenceIdBadges } from "@/features/dashboard/components/evidence-id-badges";
import type { ApplicationReport } from "@/features/dashboard/types";

interface ReportSkillEvidenceProps {
  hasUnclearJobRequirements: boolean;
  report: ApplicationReport;
}

export function ReportSkillEvidence({
  hasUnclearJobRequirements,
  report
}: ReportSkillEvidenceProps) {
  return (
    <div className="grid gap-5 xl:grid-cols-2">
      <section aria-labelledby="all-matched-skills-title">
        <div className="mb-3 flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 text-validation" aria-hidden="true" />
            <h4 className="text-sm font-bold text-foreground" id="all-matched-skills-title">
              Matched skills
            </h4>
          </div>
          <Badge tone="success">{report.matched_skills.length} linked</Badge>
        </div>

        {report.matched_skills.length > 0 ? (
          <div className="divide-y divide-border overflow-hidden rounded-xl border border-border bg-background">
            {report.matched_skills.map((item) => (
              <article className="min-w-0 p-3.5" key={item.skill}>
                <div className="flex min-w-0 flex-wrap items-center justify-between gap-2">
                  <h5 className="min-w-0 text-sm font-semibold text-foreground [overflow-wrap:anywhere]">
                    {item.skill}
                  </h5>
                  <div className="flex flex-wrap gap-2">
                    <Badge tone="success">{item.match_type}</Badge>
                    <Badge tone={confidenceTone(item.confidence)}>
                      {item.confidence} confidence
                    </Badge>
                  </div>
                </div>
                <p className="mt-2 text-xs leading-5 text-muted-foreground [overflow-wrap:anywhere]">
                  {item.job_evidence_text}
                </p>
                <EvidenceReferences evidenceIds={item.resume_evidence_ids} />
              </article>
            ))}
          </div>
        ) : (
          <EmptySkillState
            description={
              hasUnclearJobRequirements
                ? "No matches can be trusted until the job requirements are extracted."
                : "No resume evidence matched the extracted job skills."
            }
            title="No evidence-backed matches yet"
            tone={hasUnclearJobRequirements ? "warning" : "neutral"}
          />
        )}
      </section>

      <section aria-labelledby="all-skill-gaps-title">
        <div className="mb-3 flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-warning" aria-hidden="true" />
            <h4 className="text-sm font-bold text-foreground" id="all-skill-gaps-title">
              Missing or weak
            </h4>
          </div>
          <Badge tone={skillGapCount(report) > 0 ? "warning" : "success"}>
            {skillGapCount(report)} to review
          </Badge>
        </div>

        {skillGapCount(report) > 0 ? (
          <div className="divide-y divide-border overflow-hidden rounded-xl border border-border bg-background">
            {report.missing_skills.map((item) => (
              <article className="min-w-0 p-3.5" key={`missing-${item.skill}`}>
                <div className="flex min-w-0 flex-wrap items-center justify-between gap-2">
                  <h5 className="min-w-0 text-sm font-semibold text-foreground [overflow-wrap:anywhere]">
                    {item.skill}
                  </h5>
                  <Badge tone={item.importance === "required" ? "danger" : "warning"}>
                    {item.importance}
                  </Badge>
                </div>
                <p className="mt-2 text-xs leading-5 text-foreground [overflow-wrap:anywhere]">
                  {item.recommendation}
                </p>
                <p className="mt-1 text-xs leading-5 text-muted-foreground [overflow-wrap:anywhere]">
                  {item.why_it_matters}
                </p>
              </article>
            ))}
            {report.weak_skills.map((item) => (
              <article className="min-w-0 p-3.5" key={`weak-${item.skill}`}>
                <div className="flex min-w-0 flex-wrap items-center justify-between gap-2">
                  <h5 className="min-w-0 text-sm font-semibold text-foreground [overflow-wrap:anywhere]">
                    {item.skill}
                  </h5>
                  <Badge tone="warning">weak evidence</Badge>
                </div>
                <p className="mt-2 text-xs leading-5 text-muted-foreground [overflow-wrap:anywhere]">
                  {item.reason}
                </p>
                <EvidenceReferences evidenceIds={item.resume_evidence_ids} />
              </article>
            ))}
          </div>
        ) : (
          <EmptySkillState
            description={
              hasUnclearJobRequirements
                ? "Missing skills cannot be determined until explicit job requirements are extracted."
                : "No missing or weak skills were found in the extracted job evidence."
            }
            title={hasUnclearJobRequirements ? "Gaps not available" : "No gaps detected"}
            tone={hasUnclearJobRequirements ? "warning" : "neutral"}
          />
        )}
      </section>
    </div>
  );
}

function EvidenceReferences({ evidenceIds }: { evidenceIds: string[] }) {
  if (evidenceIds.length === 0) {
    return null;
  }

  return (
    <details className="group mt-2">
      <summary className="inline-flex cursor-pointer list-none items-center gap-1.5 text-xs font-semibold text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/35">
        <ChevronDown
          aria-hidden="true"
          className="h-3.5 w-3.5 transition-transform group-open:rotate-180"
        />
        View {evidenceIds.length} linked {evidenceIds.length === 1 ? "source" : "sources"}
      </summary>
      <EvidenceIdBadges evidenceIds={evidenceIds} />
    </details>
  );
}

function EmptySkillState({
  description,
  title,
  tone
}: {
  description: string;
  title: string;
  tone: "neutral" | "warning";
}) {
  return (
    <div
      className={
        tone === "warning"
          ? "rounded-xl border border-warning/25 bg-warning/10 p-4"
          : "rounded-xl border border-border bg-background p-4"
      }
    >
      <p className="text-sm font-semibold text-foreground">{title}</p>
      <p className="mt-1 text-sm leading-6 text-muted-foreground">{description}</p>
    </div>
  );
}

function confidenceTone(
  confidence: ApplicationReport["matched_skills"][number]["confidence"]
): "neutral" | "success" | "warning" {
  if (confidence === "high") {
    return "success";
  }
  if (confidence === "low") {
    return "warning";
  }
  return "neutral";
}

function skillGapCount(report: ApplicationReport): number {
  return report.missing_skills.length + report.weak_skills.length;
}
