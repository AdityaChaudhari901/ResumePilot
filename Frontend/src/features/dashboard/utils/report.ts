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
    return "Strong match";
  }

  if (band === "moderate") {
    return "Partial match";
  }

  return "Needs evidence";
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
