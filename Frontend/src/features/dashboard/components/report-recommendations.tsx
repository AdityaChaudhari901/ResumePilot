import { ChevronDown, ListChecks, SearchCheck, ShieldCheck } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { EvidenceIdBadges } from "@/features/dashboard/components/evidence-id-badges";
import type { ApplicationReport } from "@/features/dashboard/types";

interface ReportRecommendationsProps {
  hasUnclearJobRequirements: boolean;
  report: ApplicationReport;
}

export function ReportRecommendations({
  hasUnclearJobRequirements,
  report
}: ReportRecommendationsProps) {
  return (
    <div className="space-y-6">
      <div className="grid gap-5 xl:grid-cols-2">
        <section aria-labelledby="all-tailored-bullets-title">
          <div className="mb-3 flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-primary" aria-hidden="true" />
              <h4 className="text-sm font-bold text-foreground" id="all-tailored-bullets-title">
                Tailored bullets
              </h4>
            </div>
            <Badge tone="neutral">{report.tailored_bullets.length} suggestions</Badge>
          </div>

          {report.tailored_bullets.length > 0 ? (
            <div className="divide-y divide-border overflow-hidden rounded-xl border border-border bg-background">
              {report.tailored_bullets.map((item, index) => (
                <article className="min-w-0 p-3.5" key={`${item.bullet}-${index}`}>
                  <div className="flex items-start gap-3">
                    <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-primary/12 font-mono text-[0.65rem] font-semibold text-accent">
                      {String(index + 1).padStart(2, "0")}
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                        <p className="min-w-0 text-sm leading-6 text-foreground [overflow-wrap:anywhere]">
                          {item.bullet}
                        </p>
                        {item.unsupported_claims.length > 0 ? (
                          <Badge className="shrink-0" tone="warning">
                            review only
                          </Badge>
                        ) : null}
                      </div>
                      {item.jd_keywords_used.length > 0 ? (
                        <p className="mt-2 text-xs leading-5 text-muted-foreground [overflow-wrap:anywhere]">
                          Uses JD keywords: {item.jd_keywords_used.join(", ")}
                        </p>
                      ) : null}
                      <EvidenceReferences evidenceIds={item.evidence_ids} />
                    </div>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <div className="rounded-xl border border-dashed border-border-strong bg-background p-4 text-sm leading-6 text-muted-foreground">
              No project or experience evidence was strong enough for an exportable tailored
              bullet. Add truthful project/work evidence before editing the resume.
            </div>
          )}
        </section>

        <section aria-labelledby="all-ats-keywords-title">
          <div className="mb-3 flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <SearchCheck className="h-4 w-4 text-primary" aria-hidden="true" />
              <h4 className="text-sm font-bold text-foreground" id="all-ats-keywords-title">
                ATS keywords
              </h4>
            </div>
            <Badge tone="neutral">{report.ats_keywords.length} reviewed</Badge>
          </div>

          {report.ats_keywords.length > 0 ? (
            <div className="divide-y divide-border overflow-hidden rounded-xl border border-border bg-background">
              {report.ats_keywords.map((item) => (
                <article className="min-w-0 p-3.5" key={item.keyword}>
                  <div className="flex min-w-0 flex-wrap items-center justify-between gap-2">
                    <h5 className="min-w-0 text-sm font-semibold text-foreground [overflow-wrap:anywhere]">
                      {item.keyword}
                    </h5>
                    <Badge tone={keywordStatusTone(item.status)}>
                      {keywordStatusLabel(item.status)}
                    </Badge>
                  </div>
                  <p className="mt-2 text-xs leading-5 text-muted-foreground [overflow-wrap:anywhere]">
                    {item.note}
                  </p>
                  <EvidenceReferences evidenceIds={item.evidence_ids} />
                </article>
              ))}
            </div>
          ) : (
            <div className="rounded-xl border border-border bg-background p-4">
              <p className="text-sm font-semibold text-foreground">No ATS keywords extracted</p>
              <p className="mt-1 text-sm leading-6 text-muted-foreground">
                {hasUnclearJobRequirements
                  ? "The job page did not expose enough requirement evidence for safe keyword suggestions."
                  : "No supported or add-only-if-true keywords were produced for this report."}
              </p>
            </div>
          )}
        </section>
      </div>

      <section aria-labelledby="all-next-actions-title">
        <div className="mb-3 flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <ListChecks className="h-4 w-4 text-validation" aria-hidden="true" />
            <h4 className="text-sm font-bold text-foreground" id="all-next-actions-title">
              Next actions
            </h4>
          </div>
          <Badge tone="neutral">{report.next_actions.length} actions</Badge>
        </div>
        <ol className="grid gap-2 md:grid-cols-2">
          {report.next_actions.map((action, index) => (
            <li
              className="flex min-w-0 gap-3 rounded-xl border border-border bg-background p-3.5 text-sm leading-6 text-muted-foreground"
              key={action}
            >
              <span className="font-mono text-xs font-semibold text-accent">
                {String(index + 1).padStart(2, "0")}
              </span>
              <span className="min-w-0 [overflow-wrap:anywhere]">{action}</span>
            </li>
          ))}
        </ol>
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

function keywordStatusLabel(
  status: ApplicationReport["ats_keywords"][number]["status"]
): string {
  if (status === "add_only_if_true") {
    return "add only if true";
  }
  return status;
}

function keywordStatusTone(
  status: ApplicationReport["ats_keywords"][number]["status"]
): "neutral" | "success" | "warning" {
  if (status === "supported") {
    return "success";
  }
  if (status === "add_only_if_true") {
    return "warning";
  }
  return "neutral";
}
