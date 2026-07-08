import type { HTMLAttributes } from "react";

import { cn } from "@/lib/cn";

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: "neutral" | "success" | "warning" | "danger" | "primary";
}

const toneClasses: Record<NonNullable<BadgeProps["tone"]>, string> = {
  neutral: "border-border bg-muted text-muted-foreground",
  success: "border-validation/20 bg-validation/10 text-validation",
  warning: "border-warning/25 bg-warning/10 text-warning",
  danger: "border-destructive/25 bg-destructive/10 text-destructive",
  primary: "border-primary/20 bg-primary/10 text-primary"
};

export function Badge({ className, tone = "neutral", ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md border px-2 py-1 text-xs font-medium",
        toneClasses[tone],
        className
      )}
      {...props}
    />
  );
}
