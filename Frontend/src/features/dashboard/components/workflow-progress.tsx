import { CheckCircle2, Circle, CircleDot, LockKeyhole } from "lucide-react";

import { cn } from "@/lib/cn";

export type WorkflowStepId = "job" | "jobReview" | "resume" | "ai" | "report" | "draft";
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
    <nav
      aria-label="Application workflow"
      className="overflow-hidden rounded-2xl border border-border-strong bg-border shadow-[0_18px_50px_-42px_rgba(12,17,10,0.8)]"
    >
      <ol className="grid grid-cols-2 gap-px sm:grid-cols-3 xl:grid-cols-6">
        {steps.map((step, index) => {
          const Icon = statusIcon(step.status);

          return (
            <li
              aria-current={step.status === "active" ? "step" : undefined}
              className={cn(
                "relative min-h-40 bg-surface-raised p-3.5 sm:min-h-36 sm:p-4",
                step.status === "active" && "bg-primary text-primary-foreground",
                step.status === "complete" && "bg-surface text-foreground",
                step.status === "ready" && "bg-surface-raised text-foreground",
                step.status === "locked" && "bg-background text-muted-foreground"
              )}
              key={step.id}
            >
              <div className="flex items-center justify-between gap-3">
                <span
                  className={cn(
                    "font-mono text-[0.68rem] font-medium tracking-[0.12em] text-muted-foreground",
                    step.status === "active" && "text-primary-foreground/65"
                  )}
                >
                  0{index + 1}
                </span>
                <Icon
                  className={cn(
                    "h-4 w-4 shrink-0",
                    step.status === "complete" && "text-validation",
                    step.status === "active" && "text-primary-foreground",
                    step.status === "locked" && "text-muted-foreground"
                  )}
                  aria-hidden="true"
                />
              </div>
              <p className="mt-5 text-sm font-extrabold tracking-[-0.025em]">{step.label}</p>
              <p
                className={cn(
                  "mt-1 line-clamp-2 text-xs leading-5 text-muted-foreground",
                  step.status === "active" && "text-primary-foreground/70"
                )}
              >
                {step.detail}
              </p>
              <span
                className={cn(
                  "absolute bottom-3.5 left-3.5 font-mono text-[0.62rem] uppercase tracking-[0.12em] text-muted-foreground sm:bottom-4 sm:left-4",
                  step.status === "active" && "text-primary-foreground/70",
                  step.status === "complete" && "text-validation"
                )}
              >
                {statusLabel(step.status)}
              </span>
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
