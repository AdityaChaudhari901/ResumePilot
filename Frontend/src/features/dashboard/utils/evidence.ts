export type EvidenceTone = "success" | "warning" | "primary" | "neutral";

export interface EvidenceSourceDisplay {
  label: string;
  description: string;
  tone: EvidenceTone;
}

const EVIDENCE_SOURCE_RULES: Array<{
  prefix: string;
  label: string;
  description: string;
  tone: EvidenceTone;
}> = [
  {
    description: "Resume project evidence. Stronger proof because it comes from a project entry.",
    label: "Project evidence",
    prefix: "projects_",
    tone: "success"
  },
  {
    description: "Resume work experience evidence. Stronger proof because it comes from work history.",
    label: "Work evidence",
    prefix: "experience_",
    tone: "success"
  },
  {
    description: "Resume skills section evidence. Useful for ATS keywords, but weaker than project or work proof.",
    label: "Skills section",
    prefix: "skills_",
    tone: "warning"
  },
  {
    description: "Resume summary evidence. Useful context, but weaker than project or work proof.",
    label: "Resume summary",
    prefix: "summary_",
    tone: "warning"
  },
  {
    description: "Resume education evidence.",
    label: "Education evidence",
    prefix: "education_",
    tone: "primary"
  },
  {
    description: "Resume certification evidence.",
    label: "Certification evidence",
    prefix: "certifications_",
    tone: "primary"
  }
];

export function formatEvidenceSource(evidenceId: string): EvidenceSourceDisplay {
  const rule = EVIDENCE_SOURCE_RULES.find((item) => evidenceId.startsWith(item.prefix));

  if (!rule) {
    return {
      description: `Resume evidence source. Internal evidence ID: ${evidenceId}.`,
      label: "Resume evidence",
      tone: "neutral"
    };
  }

  return {
    description: `${rule.description} Internal evidence ID: ${evidenceId}.`,
    label: `${rule.label}${formatEvidenceNumber(evidenceId)}`,
    tone: rule.tone
  };
}

function formatEvidenceNumber(evidenceId: string): string {
  const match = evidenceId.match(/_(\d+)$/);
  if (!match?.[1]) {
    return "";
  }
  return ` #${Number(match[1])}`;
}
