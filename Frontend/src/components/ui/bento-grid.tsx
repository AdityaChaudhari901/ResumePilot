import type { HTMLAttributes, ReactNode } from "react";

import { cn } from "@/lib/cn";

/** Product-specific adaptation of Aceternity UI's Bento Grid primitive. */
export function BentoGrid({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("grid auto-rows-[minmax(9rem,auto)] grid-cols-1 gap-3 sm:grid-cols-2", className)}
      {...props}
    />
  );
}

interface BentoGridItemProps extends HTMLAttributes<HTMLElement> {
  eyebrow: string;
  icon: ReactNode;
  title: string;
}

export function BentoGridItem({
  children,
  className,
  eyebrow,
  icon,
  title,
  ...props
}: BentoGridItemProps) {
  return (
    <article
      className={cn(
        "group relative overflow-hidden rounded-2xl border border-border bg-surface-raised p-5 shadow-[0_14px_40px_-30px_rgba(15,20,12,0.7)]",
        className
      )}
      {...props}
    >
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-primary/70 to-transparent opacity-0 transition-opacity group-hover:opacity-100" />
      <div className="flex items-start justify-between gap-4">
        <span className="font-mono text-[0.68rem] font-medium uppercase tracking-[0.16em] text-muted-foreground">
          {eyebrow}
        </span>
        <span className="grid h-8 w-8 place-items-center rounded-lg border border-border bg-surface text-foreground">
          {icon}
        </span>
      </div>
      <h2 className="mt-8 text-lg font-bold tracking-[-0.025em] text-foreground">{title}</h2>
      <div className="mt-2 text-sm leading-6 text-muted-foreground">{children}</div>
    </article>
  );
}
