export const clerkAppearance = {
  elements: {
    rootBox: "w-full",
    cardBox: "w-full shadow-none",
    card: "w-full border-0 bg-transparent p-4 shadow-none sm:p-6",
    headerTitle: "text-2xl font-extrabold tracking-[-0.04em] text-foreground",
    headerSubtitle: "text-sm leading-6 text-muted-foreground",
    socialButtonsBlockButton:
      "h-11 rounded-lg border-border-strong bg-surface text-foreground shadow-none hover:bg-muted",
    socialButtonsBlockButtonText: "font-bold text-foreground",
    dividerLine: "bg-border",
    dividerText: "font-mono text-[0.65rem] uppercase tracking-[0.14em] text-muted-foreground",
    formFieldLabel: "text-sm font-bold text-foreground",
    formFieldInput:
      "h-11 rounded-lg border-border-strong bg-surface-inset text-foreground shadow-none focus:border-primary focus:ring-primary",
    formButtonPrimary:
      "h-11 rounded-lg bg-primary font-bold text-primary-foreground shadow-none hover:bg-primary hover:brightness-95",
    identityPreview: "rounded-xl border border-border bg-surface",
    identityPreviewText: "text-foreground",
    footer: "bg-transparent",
    footerActionText: "text-muted-foreground",
    footerActionLink: "font-bold text-foreground hover:text-accent"
  },
  variables: {
    borderRadius: "0.65rem",
    colorBackground: "var(--color-surface-raised)",
    colorDanger: "var(--color-destructive)",
    colorInputBackground: "var(--color-surface-inset)",
    colorInputText: "var(--color-foreground)",
    colorPrimary: "var(--color-primary)",
    colorText: "var(--color-foreground)",
    colorTextSecondary: "var(--color-muted-foreground)",
    fontFamily: "var(--font-sans)"
  }
} as const;
