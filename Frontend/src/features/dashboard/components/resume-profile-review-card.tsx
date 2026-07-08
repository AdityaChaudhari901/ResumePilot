import { AlertTriangle, ClipboardCheck, Mail, MapPin, Phone } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Panel } from "@/components/ui/panel";
import type { Confidence, ResumeFact, ResumeProfile } from "@/features/dashboard/types";

interface ResumeProfileReviewCardProps {
  profile: ResumeProfile | null;
}

export function ResumeProfileReviewCard({ profile }: ResumeProfileReviewCardProps) {
  if (!profile) {
    return (
      <Panel eyebrow="Review" title="Resume extraction">
        <div className="rounded-md border border-dashed border-border bg-surface p-4 text-sm text-muted-foreground">
          Upload a resume to inspect parsed evidence.
        </div>
      </Panel>
    );
  }

  const candidate = profile.candidate;
  const reviewFacts = [
    ...profile.experience.slice(0, 2),
    ...profile.projects.slice(0, 3),
    ...profile.education.slice(0, 1)
  ].slice(0, 5);
  const skillPreview = profile.skills.slice(0, 10);

  return (
    <Panel
      action={
        profile.warnings.length > 0 ? (
          <Badge tone="warning">{profile.warnings.length} warning(s)</Badge>
        ) : (
          <Badge tone="success">parsed</Badge>
        )
      }
      eyebrow="Review"
      title="Resume extraction"
    >
      <div className="space-y-4">
        <div className="rounded-md border border-border bg-surface p-3">
          <div className="flex items-start gap-2">
            <ClipboardCheck className="mt-0.5 h-4 w-4 text-validation" aria-hidden="true" />
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold">
                {candidate.name || "Candidate profile"}
              </p>
              <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground">
                {candidate.email ? (
                  <span className="inline-flex items-center gap-1">
                    <Mail className="h-3.5 w-3.5" aria-hidden="true" />
                    {candidate.email}
                  </span>
                ) : null}
                {candidate.phone ? (
                  <span className="inline-flex items-center gap-1">
                    <Phone className="h-3.5 w-3.5" aria-hidden="true" />
                    {candidate.phone}
                  </span>
                ) : null}
                {candidate.location ? (
                  <span className="inline-flex items-center gap-1">
                    <MapPin className="h-3.5 w-3.5" aria-hidden="true" />
                    {candidate.location}
                  </span>
                ) : null}
              </div>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-2">
          <ResumeStat label="Skills" value={profile.skills.length} />
          <ResumeStat label="Facts" value={profile.facts.length} />
          <ResumeStat label="Projects" value={profile.projects.length} />
        </div>

        {skillPreview.length > 0 ? (
          <section aria-labelledby="resume-skills-title">
            <h3 id="resume-skills-title" className="mb-2 text-sm font-semibold">
              Parsed skills
            </h3>
            <div className="flex flex-wrap gap-2">
              {skillPreview.map((skill) => (
                <Badge key={`${skill.name}-${skill.category}`} tone={confidenceTone(skill.confidence)}>
                  {skill.name}
                </Badge>
              ))}
            </div>
          </section>
        ) : null}

        {reviewFacts.length > 0 ? (
          <section aria-labelledby="resume-facts-title">
            <h3 id="resume-facts-title" className="mb-2 text-sm font-semibold">
              Evidence ledger
            </h3>
            <div className="space-y-2">
              {reviewFacts.map((fact) => (
                <ResumeFactRow fact={fact} key={fact.id} />
              ))}
            </div>
          </section>
        ) : null}

        {profile.warnings.length > 0 ? (
          <div className="space-y-2">
            {profile.warnings.slice(0, 3).map((warning) => (
              <div
                className="rounded-md border border-warning/25 bg-warning/10 p-3"
                key={warning.code}
              >
                <div className="flex items-start gap-2">
                  <AlertTriangle className="mt-0.5 h-4 w-4 text-warning" aria-hidden="true" />
                  <div>
                    <Badge tone="warning">{warning.code}</Badge>
                    <p className="mt-2 text-xs leading-5 text-muted-foreground">
                      {warning.message}
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : null}
      </div>
    </Panel>
  );
}

function ResumeStat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-md border border-border bg-surface p-3">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-1 font-mono text-xl font-semibold tabular-nums">{value}</p>
    </div>
  );
}

function ResumeFactRow({ fact }: { fact: ResumeFact }) {
  return (
    <div className="rounded-md border border-border bg-surface p-3">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="primary">{fact.id}</Badge>
        <Badge tone={confidenceTone(fact.confidence)}>{fact.confidence} confidence</Badge>
      </div>
      <p className="mt-2 text-xs leading-5 text-muted-foreground">{fact.text}</p>
    </div>
  );
}

function confidenceTone(confidence: Confidence): "success" | "warning" | "neutral" {
  if (confidence === "high") {
    return "success";
  }
  if (confidence === "low") {
    return "warning";
  }
  return "neutral";
}
