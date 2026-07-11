import { ChevronDown } from "lucide-react";
import type { ReactNode, Ref } from "react";

import { cn } from "@/lib/cn";

interface ReportSectionDisclosureProps {
  badge?: ReactNode;
  children: ReactNode;
  className?: string;
  description: string;
  detailsRef?: Ref<HTMLDetailsElement>;
  icon: ReactNode;
  id: string;
  title: string;
}

export function ReportSectionDisclosure({
  badge,
  children,
  className,
  description,
  detailsRef,
  icon,
  id,
  title
}: ReportSectionDisclosureProps) {
  const titleId = `${id}-title`;

  return (
    <details
      aria-labelledby={titleId}
      className={cn(
        "group overflow-hidden rounded-xl border border-border bg-surface-raised",
        className
      )}
      data-testid={`${id}-disclosure`}
      id={`${id}-details`}
      ref={detailsRef}
    >
      <summary className="relative cursor-pointer list-none p-4 transition-colors hover:bg-surface focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-primary sm:flex sm:items-start sm:justify-between sm:gap-4 sm:p-5">
        <div className="flex min-w-0 items-start gap-3 pr-7 sm:pr-0">
          <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg border border-border bg-surface text-primary">
            {icon}
          </span>
          <div className="min-w-0">
            <h3 className="text-sm font-bold tracking-[-0.02em] text-foreground" id={titleId}>
              {title}
            </h3>
            <p className="mt-1 text-xs leading-5 text-muted-foreground">{description}</p>
          </div>
        </div>
        <div className="mt-3 flex shrink-0 items-center gap-2 pl-12 sm:mt-0 sm:pl-0">
          {badge}
          <ChevronDown
            aria-hidden="true"
            className="absolute right-4 top-4 h-4 w-4 text-muted-foreground transition-transform group-open:rotate-180 sm:static"
          />
        </div>
      </summary>
      <div className="border-t border-border p-4 sm:p-5">{children}</div>
    </details>
  );
}
