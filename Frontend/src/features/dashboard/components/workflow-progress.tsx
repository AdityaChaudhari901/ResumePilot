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
    <section
      aria-label="Application workflow"
      className="overflow-x-auto rounded-xl border border-border bg-surface-raised"
      tabIndex={0}
    >
      <ol className="flex min-w-max divide-x divide-border lg:grid lg:min-w-0 lg:grid-cols-6">
        {steps.map((step, index) => {
          const Icon = statusIcon(step.status);

          return (
            <li
              aria-current={step.status === "active" ? "step" : undefined}
              className={cn(
                "relative w-40 shrink-0 bg-surface-raised px-4 py-3.5 lg:w-auto",
                step.status === "active" && "bg-primary/12 text-foreground",
                step.status === "complete" && "bg-surface text-foreground",
                step.status === "ready" && "bg-surface-raised text-foreground",
                step.status === "locked" && "bg-background text-muted-foreground"
              )}
              key={step.id}
            >
              <span
                className={cn(
                  "absolute inset-x-0 top-0 h-0.5 bg-transparent",
                  step.status === "active" && "bg-primary",
                  step.status === "complete" && "bg-validation"
                )}
                aria-hidden="true"
              />
              <div className="flex items-center justify-between gap-3">
                <span
                  className={cn(
                    "font-mono text-[0.68rem] font-medium tracking-[0.12em] text-muted-foreground",
                    step.status === "active" && "text-accent"
                  )}
                >
                  0{index + 1}
                </span>
                <Icon
                  className={cn(
                    "h-4 w-4 shrink-0",
                    step.status === "complete" && "text-validation",
                    step.status === "active" && "text-accent",
                    step.status === "locked" && "text-muted-foreground"
                  )}
                  aria-hidden="true"
                />
              </div>
              <p className="mt-3 truncate text-sm font-extrabold tracking-[-0.025em]">{step.label}</p>
              <p
                className={cn(
                  "mt-1 line-clamp-1 text-[0.7rem] leading-5 text-muted-foreground",
                  step.status === "active" && "text-foreground/70"
                )}
              >
                {step.detail}
              </p>
              <span
                className={cn(
                  "mt-2 block font-mono text-[0.6rem] uppercase tracking-[0.12em] text-muted-foreground",
                  step.status === "active" && "text-accent",
                  step.status === "complete" && "text-validation"
                )}
              >
                {statusLabel(step.status)}
              </span>
            </li>
          );
        })}
      </ol>
    </section>
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
