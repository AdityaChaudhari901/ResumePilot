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
  MatchScoreStatus,
  ScoringVersion
} from "@/features/dashboard/types";
