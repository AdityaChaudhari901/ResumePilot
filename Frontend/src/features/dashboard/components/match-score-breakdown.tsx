import { ChevronDown } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { EvidenceIdBadges } from "@/features/dashboard/components/evidence-id-badges";
import type {
  MatchScoreBreakdown,
  MatchScoreComponent,
  MatchScoreComponentKey,
  ScoringVersion
} from "@/features/dashboard/types";
import { cn } from "@/lib/cn";

interface MatchScoreBreakdownProps {
  breakdown: MatchScoreBreakdown | null | undefined;
  embedded?: boolean;
  scoringVersion: ScoringVersion | undefined;
}

const COMPONENT_LABELS: Record<MatchScoreComponentKey, string> = {
  required_skills: "Required skill evidence",
  responsibilities: "Responsibility evidence",
  preferred_skills: "Preferred skill evidence",
  experience: "Experience evidence",
  domain: "Domain evidence",
  evidence_strength: "Work/project proof"
};

export function MatchScoreBreakdownView({
  breakdown,
  embedded = false,
  scoringVersion
}: MatchScoreBreakdownProps) {
  if (!breakdown) {
    return (
      <section
        aria-label={embedded ? "Historical score calculation details" : undefined}
        aria-labelledby={embedded ? undefined : "score-breakdown-title"}
        className={cn(!embedded && "rounded-xl border border-border bg-surface p-5")}
      >
        {embedded ? null : (
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="text-sm font-semibold" id="score-breakdown-title">
              Evidence breakdown
            </h3>
            <Badge tone="neutral">{formatScoringVersion(scoringVersion)}</Badge>
          </div>
        )}
        <p className={cn("text-sm leading-6 text-muted-foreground", !embedded && "mt-2")}>
          Detailed evidence components were not recorded for this historical report. Re-running
          creates a new report whose score may differ; this saved report remains unchanged.
        </p>
      </section>
    );
  }

  return (
    <section
      aria-label={embedded ? "Evidence-fit score calculation details" : undefined}
      aria-labelledby={embedded ? undefined : "score-breakdown-title"}
      className={cn(!embedded && "rounded-xl border border-border bg-surface p-5")}
    >
      {embedded ? (
        <p className="text-xs leading-5 text-muted-foreground">
          Not-applicable dimensions are removed and reweighted. Unknown required evidence keeps
          its weight with zero contribution, so missing information cannot raise the score.
        </p>
      ) : (
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold" id="score-breakdown-title">
              How this evidence-fit score is calculated
            </h3>
            <p className="mt-1 text-xs leading-5 text-muted-foreground">
              Not-applicable dimensions are removed and reweighted. Unknown required evidence keeps
              its weight with zero contribution, so missing information cannot raise the score.
            </p>
          </div>
          <Badge tone={breakdown.score_status === "provisional" ? "warning" : "neutral"}>
            {formatScoringVersion(breakdown.scoring_version)}
          </Badge>
        </div>
      )}

      <div
        className={cn(
          "divide-y divide-border overflow-hidden rounded-xl border border-border bg-background",
          embedded ? "mt-3" : "mt-4"
        )}
      >
        {breakdown.components.map((component) => {
          const summaryId = `score-component-${component.key}-summary`;
          return (
            <article className="p-3.5 sm:p-4" key={component.key}>
              <div className="flex items-start justify-between gap-3">
                <p className="text-sm font-medium">{COMPONENT_LABELS[component.key]}</p>
                <Badge tone={componentTone(component)}>{componentValue(component)}</Badge>
              </div>
              {component.score === null || component.key === "evidence_strength" ? null : (
                <progress
                  aria-describedby={summaryId}
                  aria-label={`${COMPONENT_LABELS[component.key]} score`}
                  className="mt-3 h-2 w-full overflow-hidden rounded-full accent-primary"
                  max={100}
                  value={component.score}
                />
              )}
              <p className="mt-2 text-xs leading-5 text-muted-foreground" id={summaryId}>
                {componentSummary(component)}
              </p>
              <details className="group mt-2">
                <summary className="inline-flex cursor-pointer list-none items-center gap-1.5 text-xs font-semibold text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/35">
                  <ChevronDown
                    aria-hidden="true"
                    className="h-3.5 w-3.5 transition-transform group-open:rotate-180"
                  />
                  {component.key === "evidence_strength" ? "View explanation" : "View calculation"} and {component.evidence_ids.length} linked {component.evidence_ids.length === 1 ? "source" : "sources"}
                </summary>
                <p className="mt-2 text-xs leading-5 text-muted-foreground">
                  {componentExplanation(component)}
                </p>
                <EvidenceIdBadges evidenceIds={component.evidence_ids} />
              </details>
            </article>
          );
        })}
      </div>

      {breakdown.score_cap === null ? null : (
        <p className="mt-3 rounded-xl border border-warning/25 bg-warning/10 p-4 text-xs leading-5">
          This result is provisional and capped at {Math.round(breakdown.score_cap)}% because the
          reviewed job evidence is incomplete.
        </p>
      )}
    </section>
  );
}

function componentValue(component: MatchScoreComponent): string {
  if (component.status === "unknown") {
    return "Unknown";
  }
  if (component.status === "not_applicable") {
    return "Not listed";
  }
  if (
    component.key === "evidence_strength" &&
    component.matched_count !== null &&
    component.total_count !== null
  ) {
    return `${component.matched_count}/${component.total_count} backed`;
  }
  return `${Math.round(component.score ?? 0)}%`;
}

function componentSummary(component: MatchScoreComponent): string {
  if (component.score === null) {
    return component.status === "unknown" && component.effective_weight > 0
      ? `${component.effective_weight.toFixed(1)}% effective weight reserved at zero.`
      : "Not included in the calculated score.";
  }
  if (
    component.key === "evidence_strength" &&
    component.matched_count !== null &&
    component.total_count !== null
  ) {
    const otherSectionCount = Math.max(0, component.total_count - component.matched_count);
    return `${component.matched_count} backed by work/projects · ${otherSectionCount} from other resume sections · Does not change the fit score`;
  }
  const countSummary =
    component.matched_count === null || component.total_count === null
      ? null
      : `${component.matched_count} of ${component.total_count} supported`;
  if (component.base_weight === 0) {
    return [countSummary, "Diagnostic only; not added to the total"].filter(Boolean).join(" · ");
  }
  return [
    countSummary,
    `${component.effective_weight.toFixed(1)}% effective weight`,
    `${component.contribution.toFixed(1)} points`
  ]
    .filter(Boolean)
    .join(" · ");
}

function componentExplanation(component: MatchScoreComponent): string {
  if (component.key !== "evidence_strength") {
    return component.explanation;
  }
  return (
    "This confidence check shows how many matched skills have proof in project or work history. " +
    "The remaining matches may come from other resume sections, including Skills, Summary, " +
    "Education, or Certifications. Add truthful project or work examples when available; this " +
    "check does not add or remove fit-score points."
  );
}

function componentTone(component: MatchScoreComponent): "success" | "warning" | "neutral" {
  if (component.status !== "scored") {
    return "neutral";
  }
  return (component.score ?? 0) >= 75 ? "success" : "warning";
}

function formatScoringVersion(version: ScoringVersion | undefined): string {
  if (version === "evidence_v2") {
    return "Evidence v2";
  }
  if (version === "deterministic_v1") {
    return "Deterministic v1";
  }
  return "Legacy score";
}
