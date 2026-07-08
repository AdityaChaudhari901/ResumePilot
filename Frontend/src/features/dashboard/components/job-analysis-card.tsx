import { Loader2, Play, WandSparkles } from "lucide-react";
import type { FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Panel } from "@/components/ui/panel";
import { SAMPLE_JOB_TEXT } from "@/features/dashboard/constants";

interface JobAnalysisCardProps {
  company: string;
  isAnalyzing: boolean;
  jobText: string;
  resumeReady: boolean;
  role: string;
  onCompanyChange: (value: string) => void;
  onJobTextChange: (value: string) => void;
  onRoleChange: (value: string) => void;
  onSampleJob: () => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}

export function JobAnalysisCard({
  company,
  isAnalyzing,
  jobText,
  onCompanyChange,
  onJobTextChange,
  onRoleChange,
  onSampleJob,
  onSubmit,
  resumeReady,
  role
}: JobAnalysisCardProps) {
  return (
    <Panel
      action={
        <Button
          icon={<WandSparkles className="h-4 w-4" aria-hidden="true" />}
          onClick={onSampleJob}
          variant="secondary"
        >
          Sample
        </Button>
      }
      eyebrow="Step 02"
      title="Job evidence"
    >
      <form className="space-y-4" onSubmit={onSubmit}>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="block">
            <span className="mb-2 block text-sm font-medium text-foreground">Company</span>
            <input
              className="h-10 w-full rounded-md border border-border bg-surface-inset px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/35"
              onChange={(event) => onCompanyChange(event.target.value)}
              placeholder="Optional"
              value={company}
            />
          </label>
          <label className="block">
            <span className="mb-2 block text-sm font-medium text-foreground">Role</span>
            <input
              className="h-10 w-full rounded-md border border-border bg-surface-inset px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/35"
              onChange={(event) => onRoleChange(event.target.value)}
              placeholder="Optional"
              value={role}
            />
          </label>
        </div>
        <label className="block">
          <span className="mb-2 block text-sm font-medium text-foreground">
            Job description
          </span>
          <textarea
            className="min-h-64 w-full resize-y rounded-md border border-border bg-surface-inset px-3 py-3 text-sm leading-6 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/35"
            onChange={(event) => onJobTextChange(event.target.value)}
            placeholder={SAMPLE_JOB_TEXT}
            value={jobText}
          />
        </label>
        <div className="flex items-center justify-between gap-3">
          <p className="text-xs text-muted-foreground">{jobText.trim().length} characters</p>
          <Button
            disabled={isAnalyzing || !resumeReady || jobText.trim().length < 40}
            icon={
              isAnalyzing ? (
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
              ) : (
                <Play className="h-4 w-4" aria-hidden="true" />
              )
            }
            type="submit"
          >
            Analyze
          </Button>
        </div>
      </form>
    </Panel>
  );
}
