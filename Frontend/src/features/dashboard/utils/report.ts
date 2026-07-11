export function formatScore(score: number): string {
  return `${Math.round(score)}%`;
}

export function scoreBand(score: number): "strong" | "moderate" | "low" {
  if (score >= 75) {
    return "strong";
  }

  if (score >= 50) {
    return "moderate";
  }

  return "low";
}

export function scoreLabel(score: number): string {
  const band = scoreBand(score);
  if (band === "strong") {
    return "Strong evidence coverage";
  }

  if (band === "moderate") {
    return "Partial evidence coverage";
  }

  return "Limited evidence";
}

export function scoreTone(score: number): "success" | "warning" | "danger" {
  const band = scoreBand(score);
  if (band === "strong") {
    return "success";
  }

  if (band === "moderate") {
    return "warning";
  }

  return "danger";
}

export interface ReportScorePresentation {
  badgeLabel: string;
  badgeTone: "danger" | "neutral" | "success" | "warning";
  hasProvisionalScore: boolean;
  heading: string;
  usesEvidenceV2: boolean;
}

export function reportScorePresentation(report: ApplicationReport): ReportScorePresentation {
  const hasUnclearJobRequirements = report.validation_warnings.some(
    (warning) => warning.code === "required_skills_unclear"
  );
  const hasBlockingValidation =
    report.validation_status === "block" ||
    report.validation_warnings.some((warning) => warning.severity === "block");
  const hasProvisionalScore =
    hasUnclearJobRequirements || report.score_status === "provisional";
  const usesEvidenceV2 =
    report.scoring_version === "evidence_v2" ||
    report.score_breakdown?.scoring_version === "evidence_v2";
  const displayedScoringVersion =
    report.score_breakdown?.scoring_version ?? report.scoring_version;
  const heading = usesEvidenceV2
    ? hasProvisionalScore
      ? "Provisional evidence-fit score"
      : "Evidence-fit score"
    : displayedScoringVersion === "deterministic_v1"
      ? hasProvisionalScore
        ? "Provisional deterministic v1 score"
        : "Deterministic v1 score"
      : hasProvisionalScore
        ? "Provisional legacy score"
        : "Legacy unversioned score";
  const badgeTone = hasUnclearJobRequirements
    ? "danger"
    : hasBlockingValidation
      ? "danger"
      : hasProvisionalScore
        ? "warning"
        : usesEvidenceV2
          ? scoreTone(report.match_score)
          : "neutral";
  const badgeLabel = hasUnclearJobRequirements
    ? "Needs job details"
    : hasBlockingValidation
      ? "Validation blocked"
      : hasProvisionalScore
        ? usesEvidenceV2
          ? "Provisional, evidence incomplete"
          : "Historical score, provisional"
        : usesEvidenceV2
          ? scoreLabel(report.match_score)
          : "Historical score";

  return {
    badgeLabel,
    badgeTone,
    hasProvisionalScore,
    heading,
    usesEvidenceV2
  };
}

export function scoreMetricLabel(
  version: ScoringVersion | null | undefined,
  status?: MatchScoreStatus | null
): string {
  const metric =
    version === "evidence_v2"
      ? "Evidence fit"
      : version === "deterministic_v1"
        ? "Deterministic v1"
        : "Legacy score";
  return status === "provisional" ? `${metric} · Provisional` : metric;
}
import type {
  ApplicationReport,
  MatchScoreStatus,
  ScoringVersion
} from "@/features/dashboard/types";
