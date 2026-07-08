import { proxyBackendResponse } from "@/lib/backend";

export const dynamic = "force-dynamic";

interface ReportPdfRouteContext {
  params: Promise<{
    reportId: string;
  }>;
}

export async function GET(_request: Request, context: ReportPdfRouteContext) {
  const { reportId } = await context.params;
  return proxyBackendResponse(`/reports/${encodeURIComponent(reportId)}/resume/pdf`);
}
