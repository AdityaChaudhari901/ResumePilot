import { proxyBackendResponse } from "@/lib/backend";

export const dynamic = "force-dynamic";

interface ReportDocxRouteContext {
  params: Promise<{
    reportId: string;
  }>;
}

export async function POST(request: Request, context: ReportDocxRouteContext) {
  const { reportId } = await context.params;
  return proxyBackendResponse(`/reports/${encodeURIComponent(reportId)}/resume/docx`, undefined, {
    request
  });
}
