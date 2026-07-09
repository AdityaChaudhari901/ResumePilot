import { Link2, Loader2, Play, WandSparkles } from "lucide-react";
import type { FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Panel } from "@/components/ui/panel";

interface JobAnalysisCardProps {
  company: string;
  isAnalyzing: boolean;
  jobUrl: string;
  resumeReady: boolean;
  role: string;
  onCompanyChange: (value: string) => void;
  onJobUrlChange: (value: string) => void;
  onRoleChange: (value: string) => void;
  onSampleJob: () => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}

export function JobAnalysisCard({
  company,
  isAnalyzing,
  jobUrl,
  onCompanyChange,
  onJobUrlChange,
  onRoleChange,
  onSampleJob,
  onSubmit,
  resumeReady,
  role
}: JobAnalysisCardProps) {
  const canAnalyze = resumeReady && !isAnalyzing && jobUrl.trim().length > 0;

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
            Job posting URL
          </span>
          <input
            className="h-10 w-full rounded-md border border-border bg-surface-inset px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/35"
            onChange={(event) => onJobUrlChange(event.target.value)}
            placeholder="https://company.com/jobs/backend-engineer"
            type="url"
            value={jobUrl}
          />
        </label>
        <div className="flex items-center justify-between gap-3">
          <p className="inline-flex items-center gap-2 text-xs text-muted-foreground">
            <Link2 className="h-3.5 w-3.5" aria-hidden="true" />
            Public job posting URL
          </p>
          <Button
            disabled={!canAnalyze}
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
