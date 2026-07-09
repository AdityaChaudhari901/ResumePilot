import { CheckCircle2, Circle, CircleDot, LockKeyhole } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/cn";

export type WorkflowStepId = "job" | "jobReview" | "resume" | "ai" | "report";
export type WorkflowStepStatus = "active" | "complete" | "locked" | "ready";

export interface WorkflowProgressStep {
  id: WorkflowStepId;
  label: string;
  detail: string;
  status: WorkflowStepStatus;
}

interface WorkflowProgressProps {
  steps: WorkflowProgressStep[];
}

export function WorkflowProgress({ steps }: WorkflowProgressProps) {
  return (
    <nav aria-label="Application workflow" className="rounded-lg border border-border bg-surface-raised p-3 shadow-sm">
      <ol className="grid gap-2 md:grid-cols-5">
        {steps.map((step, index) => {
          const Icon = statusIcon(step.status);

          return (
            <li
              className={cn(
                "rounded-md border p-3",
                step.status === "active" &&
                  "border-primary/35 bg-primary/10 text-foreground",
                step.status === "complete" &&
                  "border-validation/25 bg-validation/10 text-foreground",
                step.status === "ready" && "border-border bg-surface text-foreground",
                step.status === "locked" &&
                  "border-border bg-background text-muted-foreground opacity-75"
              )}
              key={step.id}
            >
              <div className="flex items-center justify-between gap-3">
                <div className="flex min-w-0 items-center gap-2">
                  <Icon
                    className={cn(
                      "h-4 w-4 shrink-0",
                      step.status === "complete" && "text-validation",
                      step.status === "active" && "text-primary",
                      step.status === "locked" && "text-muted-foreground"
                    )}
                    aria-hidden="true"
                  />
                  <p className="truncate text-sm font-semibold">{step.label}</p>
                </div>
                <Badge tone={statusTone(step.status)}>{statusLabel(step.status)}</Badge>
              </div>
              <p className="mt-2 line-clamp-2 text-xs leading-5 text-muted-foreground">
                {index + 1}. {step.detail}
              </p>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

function statusIcon(status: WorkflowStepStatus) {
  if (status === "complete") {
    return CheckCircle2;
  }
  if (status === "active") {
    return CircleDot;
  }
  if (status === "locked") {
    return LockKeyhole;
  }
  return Circle;
}

function statusLabel(status: WorkflowStepStatus): string {
  if (status === "active") {
    return "Now";
  }
  if (status === "complete") {
    return "Done";
  }
  if (status === "locked") {
    return "Locked";
  }
  return "Ready";
}

function statusTone(
  status: WorkflowStepStatus
): "neutral" | "success" | "warning" | "danger" | "primary" {
  if (status === "active") {
    return "primary";
  }
  if (status === "complete") {
    return "success";
  }
  return "neutral";
}
