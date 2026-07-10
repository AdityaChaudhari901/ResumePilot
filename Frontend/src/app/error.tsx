"use client";

import { Home, RotateCcw, TriangleAlert } from "lucide-react";

import { StatusPage } from "@/components/status-page";
import { Button } from "@/components/ui/button";
import { ButtonLink } from "@/components/ui/button-link";

export default function ErrorPage({
  reset
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <StatusPage
      actions={
        <>
          <Button
            icon={<RotateCcw className="h-4 w-4" aria-hidden="true" />}
            onClick={reset}
          >
            Try again
          </Button>
          <ButtonLink
            href="/"
            icon={<Home className="h-4 w-4" aria-hidden="true" />}
            variant="secondary"
          >
            Return home
          </ButtonLink>
        </>
      }
      description="The current view could not be completed safely. Retry to refresh its latest saved state, or return to the workspace."
      eyebrow="Recovery / Safe stop"
      icon={<TriangleAlert className="h-5 w-5 text-warning" aria-hidden="true" />}
      title="The workspace stopped before making assumptions."
    />
  );
}
