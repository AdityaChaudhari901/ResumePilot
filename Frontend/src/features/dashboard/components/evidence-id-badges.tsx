import { Badge } from "@/components/ui/badge";
import { formatEvidenceSource } from "@/features/dashboard/utils/evidence";

export function EvidenceIdBadges({ evidenceIds }: { evidenceIds: string[] }) {
  if (evidenceIds.length === 0) {
    return null;
  }

  return (
    <div className="mt-2 flex flex-wrap gap-2">
      {evidenceIds.map((evidenceId) => {
        const evidence = formatEvidenceSource(evidenceId);

        return (
          <Badge
            aria-label={evidence.description}
            key={evidenceId}
            title={evidence.description}
            tone={evidence.tone}
          >
            {evidence.label}
          </Badge>
        );
      })}
    </div>
  );
}
