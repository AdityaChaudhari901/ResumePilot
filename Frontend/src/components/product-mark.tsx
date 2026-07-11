import Link from "next/link";

import { cn } from "@/lib/cn";

interface ProductMarkProps {
  className?: string;
  href?: string;
  showWordmark?: boolean;
}

export function ProductMark({ className, href = "/", showWordmark = true }: ProductMarkProps) {
  return (
    <Link
      aria-label="ResumePilot home"
      className={cn(
        "inline-flex items-center gap-2.5 rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background",
        className
      )}
      href={href}
    >
      <span
        aria-hidden="true"
        className="relative grid h-9 w-9 shrink-0 place-items-center overflow-hidden rounded-lg bg-foreground font-mono text-sm font-semibold text-background shadow-[inset_0_0_0_1px_color-mix(in_srgb,var(--color-background)_16%,transparent)]"
      >
        RP
        <span className="absolute right-0 top-0 h-2.5 w-2.5 bg-primary" />
      </span>
      {showWordmark ? (
        <span className="text-[0.98rem] font-extrabold tracking-[-0.035em] text-foreground">
          Resume<span className="font-medium text-muted-foreground">Pilot</span>
        </span>
      ) : null}
    </Link>
  );
}
