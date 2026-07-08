import { proxyBackendResponse } from "@/lib/backend";

export const dynamic = "force-dynamic";

interface ReportLatexRouteContext {
  params: Promise<{
    reportId: string;
  }>;
}

export async function GET(_request: Request, context: ReportLatexRouteContext) {
  const { reportId } = await context.params;
  return proxyBackendResponse(`/reports/${encodeURIComponent(reportId)}/resume/latex`);
}
