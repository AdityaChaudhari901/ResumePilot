import { proxyBackendResponse } from "@/lib/backend";

export const dynamic = "force-dynamic";

interface ReportTraceRouteContext {
  params: Promise<{
    reportId: string;
  }>;
}

export async function GET(_request: Request, context: ReportTraceRouteContext) {
  const { reportId } = await context.params;
  return proxyBackendResponse(`/reports/${encodeURIComponent(reportId)}/trace`);
}
