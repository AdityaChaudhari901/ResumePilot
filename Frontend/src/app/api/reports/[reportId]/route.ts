import { proxyBackendResponse } from "@/lib/backend";

export const dynamic = "force-dynamic";

interface ReportRouteContext {
  params: Promise<{
    reportId: string;
  }>;
}

export async function GET(request: Request, context: ReportRouteContext) {
  const { reportId } = await context.params;
  return proxyBackendResponse(`/reports/${encodeURIComponent(reportId)}`, undefined, { request });
}
