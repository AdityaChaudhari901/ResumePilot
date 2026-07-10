import { ArrowLeft, FileQuestion } from "lucide-react";
import type { Metadata } from "next";

import { StatusPage } from "@/components/status-page";
import { ButtonLink } from "@/components/ui/button-link";

export const metadata: Metadata = {
  title: "Page not found"
};

export default function NotFound() {
  return (
    <StatusPage
      actions={
        <ButtonLink href="/" icon={<ArrowLeft className="h-4 w-4" aria-hidden="true" />}>
          Return to ResumePilot
        </ButtonLink>
      }
      description="The address does not point to a ResumePilot workspace or public page. Return home to continue from a verified route."
      eyebrow="404 / Route not found"
      icon={<FileQuestion className="h-5 w-5" aria-hidden="true" />}
      title="This page is outside the evidence trail."
    />
  );
}
