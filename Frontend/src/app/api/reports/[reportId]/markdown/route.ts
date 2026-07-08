import { proxyBackendResponse } from "@/lib/backend";

export const dynamic = "force-dynamic";

interface ReportMarkdownRouteContext {
  params: Promise<{
    reportId: string;
  }>;
}

export async function GET(request: Request, context: ReportMarkdownRouteContext) {
  const { reportId } = await context.params;
  return proxyBackendResponse(`/reports/${encodeURIComponent(reportId)}/markdown`, undefined, {
    request
  });
}
