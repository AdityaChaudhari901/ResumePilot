import {
  Bot,
  FileSearch,
  GitBranch,
  Loader2,
  Play,
  SearchCheck,
  ShieldCheck
} from "lucide-react";
import type { FormEvent } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Panel } from "@/components/ui/panel";
import type { UsageSummaryResponse } from "@/features/dashboard/types";

interface AiWorkflowCardProps {
  canAnalyze: boolean;
  isAnalyzing: boolean;
  usage: UsageSummaryResponse | null;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}

const WORKFLOW_ITEMS = [
  {
    description: "Fetch and normalize the public job listing into structured requirements.",
    icon: FileSearch,
    label: "Parse job evidence"
  },
  {
    description: "Compare role requirements against parsed resume facts and evidence IDs.",
    icon: SearchCheck,
    label: "Match resume evidence"
  },
  {
    description: "Draft ATS keywords, resume bullets, cover letter, and interview prep.",
    icon: Bot,
    label: "Generate application assets"
  },
  {
    description: "Reject unsupported claims before the report is shown or exported.",
    icon: ShieldCheck,
    label: "Validate output"
  }
];

export function AiWorkflowCard({
  canAnalyze,
  isAnalyzing,
  onSubmit,
  usage
}: AiWorkflowCardProps) {
  const workflowMode = usage?.live_crewai_enabled ? "Live CrewAI eligible" : "Deterministic gate";

  return (
    <Panel
      action={<Badge tone={usage?.live_crewai_enabled ? "primary" : "neutral"}>{workflowMode}</Badge>}
      eyebrow="Step 04"
      title="AI services"
    >
      <form className="space-y-5" onSubmit={onSubmit}>
        <div className="rounded-lg border border-border bg-surface p-4">
          <div className="flex items-start gap-3">
            <GitBranch className="mt-0.5 h-5 w-5 text-primary" aria-hidden="true" />
            <div>
              <p className="text-sm font-semibold text-foreground">
                ResumePilot now has both inputs.
              </p>
              <p className="mt-1 text-sm leading-6 text-muted-foreground">
                Run the evidence-first workflow to produce the validated job-fit report and export
                ready application material.
              </p>
            </div>
          </div>
        </div>

        <ol className="grid gap-3 md:grid-cols-2">
          {WORKFLOW_ITEMS.map((item, index) => {
            const Icon = item.icon;

            return (
              <li className="rounded-md border border-border bg-surface p-3" key={item.label}>
                <div className="flex items-start gap-3">
                  <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-primary/20 bg-primary/10 font-mono text-xs font-semibold text-primary">
                    {index + 1}
                  </span>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <Icon className="h-4 w-4 text-primary" aria-hidden="true" />
                      <p className="text-sm font-semibold text-foreground">{item.label}</p>
                    </div>
                    <p className="mt-1 text-xs leading-5 text-muted-foreground">
                      {item.description}
                    </p>
                  </div>
                </div>
              </li>
            );
          })}
        </ol>

        <div className="flex flex-col gap-3 border-t border-border pt-4 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-xs leading-5 text-muted-foreground">
            The backend decides whether to use live CrewAI or deterministic fallback based on plan,
            provider readiness, and validation safety.
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
            Run AI analysis
          </Button>
        </div>
      </form>
    </Panel>
  );
}
