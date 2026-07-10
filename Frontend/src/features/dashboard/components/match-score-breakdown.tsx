import { Badge } from "@/components/ui/badge";
import { EvidenceIdBadges } from "@/features/dashboard/components/evidence-id-badges";
import type {
  MatchScoreBreakdown,
  MatchScoreComponent,
  MatchScoreComponentKey,
  ScoringVersion
} from "@/features/dashboard/types";

interface MatchScoreBreakdownProps {
  breakdown: MatchScoreBreakdown | null | undefined;
  scoringVersion: ScoringVersion | undefined;
}

const COMPONENT_LABELS: Record<MatchScoreComponentKey, string> = {
  required_skills: "Required skill evidence",
  responsibilities: "Responsibility evidence",
  preferred_skills: "Preferred skill evidence",
  experience: "Experience evidence",
  domain: "Domain evidence",
  evidence_strength: "Project/work evidence strength"
};

export function MatchScoreBreakdownView({
  breakdown,
  scoringVersion
}: MatchScoreBreakdownProps) {
  if (!breakdown) {
    return (
      <section
        aria-labelledby="score-breakdown-title"
        className="rounded-lg border border-border bg-surface p-4"
      >
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-sm font-semibold" id="score-breakdown-title">
            Evidence breakdown
          </h3>
          <Badge tone="neutral">{formatScoringVersion(scoringVersion)}</Badge>
        </div>
        <p className="mt-2 text-sm leading-6 text-muted-foreground">
          Detailed evidence components were not recorded for this historical report. Re-running
          creates a new report whose score may differ; this saved report remains unchanged.
        </p>
      </section>
    );
  }

  return (
    <section
      aria-labelledby="score-breakdown-title"
      className="rounded-lg border border-border bg-surface p-4"
    >
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

      <div className="mt-4 grid gap-3 md:grid-cols-2">
        {breakdown.components.map((component) => {
          const detailsId = `score-component-${component.key}-details`;
          return (
            <div className="rounded-md border border-border bg-background p-3" key={component.key}>
              <div className="flex items-start justify-between gap-3">
                <p className="text-sm font-medium">{COMPONENT_LABELS[component.key]}</p>
                <Badge tone={componentTone(component)}>{componentValue(component)}</Badge>
              </div>
              {component.score === null ? null : (
                <progress
                  aria-describedby={detailsId}
                  aria-label={`${COMPONENT_LABELS[component.key]} score`}
                  className="mt-3 h-2 w-full overflow-hidden rounded-full accent-primary"
                  max={100}
                  value={component.score}
                />
              )}
              <div id={detailsId}>
                <p className="mt-2 text-xs leading-5 text-muted-foreground">
                  {componentSummary(component)}
                </p>
                <p className="mt-1 text-xs leading-5 text-muted-foreground">
                  {component.explanation}
                </p>
                <EvidenceIdBadges evidenceIds={component.evidence_ids} />
              </div>
            </div>
          );
        })}
      </div>

      {breakdown.score_cap === null ? null : (
        <p className="mt-3 rounded-md border border-warning/25 bg-warning/10 p-3 text-xs leading-5">
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
  return `${Math.round(component.score ?? 0)}%`;
}

function componentSummary(component: MatchScoreComponent): string {
  if (component.score === null) {
    return component.status === "unknown" && component.effective_weight > 0
      ? `${component.effective_weight.toFixed(1)}% effective weight reserved at zero.`
      : "Not included in the calculated score.";
  }
  const countSummary =
    component.matched_count === null || component.total_count === null
      ? null
      : component.key === "evidence_strength"
        ? `${component.matched_count} of ${component.total_count} have project/work support`
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
