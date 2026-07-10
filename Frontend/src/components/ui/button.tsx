import type { ButtonHTMLAttributes, ReactNode } from "react";

import { cn } from "@/lib/cn";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  icon?: ReactNode;
  variant?: "primary" | "secondary" | "ghost";
}

const variantClasses: Record<NonNullable<ButtonProps["variant"]>, string> = {
  primary:
    "border border-primary bg-primary text-primary-foreground shadow-[0_8px_24px_-14px_color-mix(in_srgb,var(--color-primary)_85%,transparent)] hover:brightness-95",
  secondary:
    "border border-border-strong bg-surface-raised text-foreground shadow-sm hover:border-foreground/30 hover:bg-surface",
  ghost: "border border-transparent text-muted-foreground hover:bg-muted hover:text-foreground"
};

export function Button({
  children,
  className,
  disabled,
  icon,
  type = "button",
  variant = "primary",
  ...props
}: ButtonProps) {
  return (
    <button
      className={cn(
        "inline-flex h-10 items-center justify-center gap-2 rounded-lg px-4 text-sm font-bold tracking-[-0.01em] transition-[background-color,border-color,color,box-shadow,filter,transform] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background active:translate-y-px disabled:pointer-events-none disabled:opacity-45 disabled:shadow-none",
        variantClasses[variant],
        className
      )}
      disabled={disabled}
      type={type}
      {...props}
    >
      {icon}
      {children}
    </button>
  );
}
