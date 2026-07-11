import type { HTMLAttributes, ReactNode } from "react";

import { cn } from "@/lib/cn";

interface PanelProps extends HTMLAttributes<HTMLElement> {
  as?: "section" | "article" | "aside";
  eyebrow?: string;
  title?: string;
  action?: ReactNode;
}

export function Panel({
  action,
  as: Component = "section",
  children,
  className,
  eyebrow,
  title,
  ...props
}: PanelProps) {
  return (
    <Component
      className={cn(
        "min-w-0 rounded-2xl border border-border bg-surface-raised p-5 shadow-[0_18px_55px_-42px_rgba(12,17,10,0.85)] sm:p-6",
        className
      )}
      {...props}
    >
      {(eyebrow || title || action) && (
        <div className="mb-5 flex flex-col items-stretch gap-4 border-b border-border pb-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            {eyebrow && (
              <p className="font-mono text-[0.68rem] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                {eyebrow}
              </p>
            )}
            {title && (
              <h2 className="mt-1.5 text-xl font-extrabold tracking-[-0.035em] text-foreground">
                {title}
              </h2>
            )}
          </div>
          {action}
        </div>
      )}
      {children}
    </Component>
  );
}
