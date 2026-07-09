import { ArrowRight, BriefcaseBusiness, Loader2 } from "lucide-react";
import type { FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Panel } from "@/components/ui/panel";

interface JobListingCardProps {
  isPreviewing: boolean;
  isJobUrlValid: boolean;
  jobUrl: string;
  onJobUrlChange: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}

export function JobListingCard({
  isPreviewing,
  isJobUrlValid,
  jobUrl,
  onJobUrlChange,
  onSubmit
}: JobListingCardProps) {
  return (
    <Panel
      eyebrow="Step 01"
      title="Job listing"
    >
      <form className="space-y-5" onSubmit={onSubmit}>
        <div className="rounded-lg border border-primary/15 bg-primary/5 p-4">
          <div className="flex items-start gap-3">
            <BriefcaseBusiness className="mt-0.5 h-5 w-5 text-primary" aria-hidden="true" />
            <div>
              <p className="text-sm font-semibold text-foreground">Start with the job URL.</p>
              <p className="mt-1 text-sm leading-6 text-muted-foreground">
                ResumePilot first reads the public job listing, then uses your uploaded resume as
                the evidence source for matching and generated suggestions.
              </p>
            </div>
          </div>
        </div>

        <label className="block">
          <span className="mb-2 block text-sm font-medium text-foreground">
            Job listing URL
          </span>
          <input
            className="h-11 w-full rounded-md border border-border bg-surface-inset px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/35"
            onChange={(event) => onJobUrlChange(event.target.value)}
            placeholder="https://company.com/jobs/backend-engineer"
            type="url"
            value={jobUrl}
          />
        </label>

        <div className="flex justify-end">
          <Button
            disabled={!isJobUrlValid || isPreviewing}
            icon={
              isPreviewing ? (
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
              ) : (
                <ArrowRight className="h-4 w-4" aria-hidden="true" />
              )
            }
            type="submit"
          >
            Review job evidence
          </Button>
        </div>
      </form>
    </Panel>
  );
}
