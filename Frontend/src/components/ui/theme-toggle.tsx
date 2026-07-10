"use client";

import { Moon, Sun } from "lucide-react";
import { useEffect, useSyncExternalStore } from "react";

import { cn } from "@/lib/cn";

type Theme = "dark" | "light";

const STORAGE_KEY = "resumepilot-theme";
const THEME_CHANGE_EVENT = "resumepilot-theme-change";

function getThemeSnapshot(): Theme {
  const explicitTheme = document.documentElement.dataset.theme;
  if (explicitTheme === "dark" || explicitTheme === "light") {
    return explicitTheme;
  }
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function getServerThemeSnapshot(): Theme {
  return "light";
}

function subscribeToTheme(onStoreChange: () => void): () => void {
  const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
  mediaQuery.addEventListener("change", onStoreChange);
  window.addEventListener(THEME_CHANGE_EVENT, onStoreChange);
  return () => {
    mediaQuery.removeEventListener("change", onStoreChange);
    window.removeEventListener(THEME_CHANGE_EVENT, onStoreChange);
  };
}

export function ThemeToggle({ className }: { className?: string }) {
  const theme = useSyncExternalStore(
    subscribeToTheme,
    getThemeSnapshot,
    getServerThemeSnapshot
  );

  useEffect(() => {
    let storedTheme: string | null = null;
    try {
      storedTheme = window.localStorage.getItem(STORAGE_KEY);
    } catch {
      // Storage can be unavailable in hardened browser contexts. System preference remains valid.
    }
    if (storedTheme === "dark" || storedTheme === "light") {
      document.documentElement.dataset.theme = storedTheme;
      window.dispatchEvent(new Event(THEME_CHANGE_EVENT));
    }
  }, []);

  function toggleTheme() {
    const nextTheme: Theme = theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = nextTheme;
    try {
      window.localStorage.setItem(STORAGE_KEY, nextTheme);
    } catch {
      // The selected theme still applies for the current page when storage is unavailable.
    }
    window.dispatchEvent(new Event(THEME_CHANGE_EVENT));
  }

  const nextThemeLabel = theme === "dark" ? "light" : "dark";

  return (
    <button
      aria-label={`Switch to ${nextThemeLabel} theme`}
      className={cn(
        "inline-flex h-9 w-9 items-center justify-center rounded-lg border border-border bg-surface-raised text-muted-foreground shadow-sm transition hover:border-border-strong hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background",
        className
      )}
      onClick={toggleTheme}
      title={`Switch to ${nextThemeLabel} theme`}
      type="button"
    >
      {theme === "dark" ? (
        <Sun className="h-4 w-4" aria-hidden="true" />
      ) : (
        <Moon className="h-4 w-4" aria-hidden="true" />
      )}
    </button>
  );
}
