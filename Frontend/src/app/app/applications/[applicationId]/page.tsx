import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { WorkspaceRoute } from "@/features/dashboard/components/workspace-route";
import { parsePositiveSafeInteger } from "@/features/dashboard/utils/route-params";

export const metadata: Metadata = {
  title: "Application"
};

interface ApplicationPageProps {
  params: Promise<{
    applicationId: string;
  }>;
}

export default async function ApplicationPage({ params }: ApplicationPageProps) {
  const { applicationId } = await params;
  const parsedApplicationId = parsePositiveSafeInteger(applicationId);
  if (parsedApplicationId === null) {
    notFound();
  }

  return <WorkspaceRoute initialApplicationId={parsedApplicationId} view="application" />;
}
