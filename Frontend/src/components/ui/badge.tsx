import type { HTMLAttributes } from "react";

import { cn } from "@/lib/cn";

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: "neutral" | "success" | "warning" | "danger" | "primary";
}

const toneClasses: Record<NonNullable<BadgeProps["tone"]>, string> = {
  neutral: "border-border-strong bg-surface-inset text-muted-foreground",
  success: "border-validation/30 bg-validation/10 text-validation",
  warning: "border-warning/35 bg-warning/10 text-warning",
  danger: "border-destructive/35 bg-destructive/10 text-destructive",
  primary: "border-primary bg-primary text-primary-foreground"
};

export function Badge({ className, tone = "neutral", ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex min-h-6 items-center rounded-full border px-2.5 py-1 font-mono text-[0.68rem] font-medium leading-none tracking-[-0.01em]",
        toneClasses[tone],
        className
      )}
      {...props}
    />
  );
}
