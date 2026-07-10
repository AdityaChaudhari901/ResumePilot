import { ArrowRight, BriefcaseBusiness, ClipboardPaste, Link2, Loader2 } from "lucide-react";
import type { FormEvent, ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Panel } from "@/components/ui/panel";
import type { JobSourceType } from "@/features/dashboard/types";

export const MAX_JOB_TEXT_CHARS = 50_000;
export const MIN_JOB_TEXT_CHARS = 40;

interface JobListingCardProps {
  isPreviewing: boolean;
  isJobInputValid: boolean;
  jobSourceType: JobSourceType;
  jobText: string;
  jobUrl: string;
  onJobSourceTypeChange: (value: JobSourceType) => void;
  onJobTextChange: (value: string) => void;
  onJobUrlChange: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}

export function JobListingCard({
  isPreviewing,
  isJobInputValid,
  jobSourceType,
  jobText,
  jobUrl,
  onJobSourceTypeChange,
  onJobTextChange,
  onJobUrlChange,
  onSubmit
}: JobListingCardProps) {
  return (
    <Panel
      eyebrow="Step 01"
      title="Job listing"
    >
      <form className="space-y-6" onSubmit={onSubmit}>
        <div className="border-l-2 border-primary bg-surface px-4 py-3">
          <div className="flex items-start gap-3">
            <BriefcaseBusiness className="mt-0.5 h-5 w-5 text-primary" aria-hidden="true" />
            <div>
              <p className="text-sm font-semibold text-foreground">Start with the job description.</p>
              <p className="mt-1 text-sm leading-6 text-muted-foreground">
                Use a public URL, or paste the description when a listing is private, blocked, or
                rendered by a site ResumePilot cannot read.
              </p>
            </div>
          </div>
        </div>

        <fieldset>
          <legend className="text-sm font-medium text-foreground">Job source</legend>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            <SourceOption
              checked={jobSourceType === "url"}
              description="Fetch a public listing"
              icon={<Link2 className="h-4 w-4" aria-hidden="true" />}
              label="Job URL"
              onChange={() => onJobSourceTypeChange("url")}
              value="url"
            />
            <SourceOption
              checked={jobSourceType === "pasted_text"}
              description="Best for blocked or private pages"
              icon={<ClipboardPaste className="h-4 w-4" aria-hidden="true" />}
              label="Paste description"
              onChange={() => onJobSourceTypeChange("pasted_text")}
              value="pasted_text"
            />
          </div>
        </fieldset>

        {jobSourceType === "url" ? (
          <label className="block">
            <span className="mb-2 block text-sm font-medium text-foreground">
              Job listing URL
            </span>
            <input
              autoComplete="url"
              className="h-12 w-full rounded-lg border border-border-strong bg-surface-inset px-4 text-sm shadow-inner focus-visible:border-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30"
              onChange={(event) => onJobUrlChange(event.target.value)}
              placeholder="https://company.com/jobs/backend-engineer"
              type="url"
              value={jobUrl}
            />
          </label>
        ) : (
          <label className="block">
            <span className="mb-2 block text-sm font-medium text-foreground">
              Job description
            </span>
            <textarea
              aria-describedby="job-description-help"
              className="min-h-64 w-full resize-y rounded-lg border border-border-strong bg-surface-inset px-4 py-3 text-sm leading-6 shadow-inner focus-visible:border-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30"
              maxLength={MAX_JOB_TEXT_CHARS}
              onChange={(event) => onJobTextChange(event.target.value)}
              placeholder="Paste the complete role, requirements, and responsibilities…"
              value={jobText}
            />
            <span
              className="mt-2 flex flex-col gap-1 text-xs text-muted-foreground sm:flex-row sm:items-center sm:justify-between"
              id="job-description-help"
            >
              Include at least {MIN_JOB_TEXT_CHARS} characters and keep the original requirements.
              <span className="font-mono tabular-nums" id="job-description-count">
                {jobText.length.toLocaleString()} / {MAX_JOB_TEXT_CHARS.toLocaleString()}
              </span>
            </span>
          </label>
        )}

        <div className="flex justify-end border-t border-border pt-5">
          <Button
            className="w-full sm:w-auto"
            disabled={!isJobInputValid || isPreviewing}
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

function SourceOption({
  checked,
  description,
  icon,
  label,
  onChange,
  value
}: {
  checked: boolean;
  description: string;
  icon: ReactNode;
  label: string;
  onChange: () => void;
  value: JobSourceType;
}) {
  return (
    <label className="cursor-pointer rounded-xl border border-border-strong bg-surface p-4 transition-colors hover:bg-muted has-[:checked]:border-primary has-[:checked]:bg-primary/10">
      <span className="flex items-start gap-3">
        <input
          checked={checked}
          className="mt-1 h-4 w-4 accent-primary"
          name="job-source"
          onChange={onChange}
          type="radio"
          value={value}
        />
        <span className="min-w-0">
          <span className="flex items-center gap-2 text-sm font-semibold text-foreground">
            {icon}
            {label}
          </span>
          <span className="mt-1 block text-xs leading-5 text-muted-foreground">{description}</span>
        </span>
      </span>
    </label>
  );
}
