import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { WorkspaceRoute } from "@/features/dashboard/components/workspace-route";
import { parsePositiveSafeInteger } from "@/features/dashboard/utils/route-params";

export const metadata: Metadata = {
  title: "Report"
};

interface ReportDetailPageProps {
  params: Promise<{
    reportId: string;
  }>;
}

export default async function ReportDetailPage({ params }: ReportDetailPageProps) {
  const { reportId } = await params;
  const parsedReportId = parsePositiveSafeInteger(reportId);
  if (parsedReportId === null) {
    notFound();
  }

  return <WorkspaceRoute initialReportId={parsedReportId} view="reportDetail" />;
}
