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
      className={cn("rounded-lg border border-border bg-surface-raised p-4 shadow-sm", className)}
      {...props}
    >
      {(eyebrow || title || action) && (
        <div className="mb-4 flex items-start justify-between gap-3">
          <div>
            {eyebrow && (
              <p className="text-xs font-semibold uppercase tracking-normal text-muted-foreground">
                {eyebrow}
              </p>
            )}
            {title && <h2 className="mt-1 text-lg font-semibold text-foreground">{title}</h2>}
          </div>
          {action}
        </div>
      )}
      {children}
    </Component>
  );
}
