import { proxyBackendResponse } from "@/lib/backend";

export const dynamic = "force-dynamic";

interface RouteContext {
  params: Promise<{
    applicationId: string;
  }>;
}

export async function POST(request: Request, context: RouteContext) {
  const { applicationId } = await context.params;
  return proxyBackendResponse(
    `/applications/${encodeURIComponent(applicationId)}/tailored-resume/docx`,
    undefined,
    {
      request
    }
  );
}
