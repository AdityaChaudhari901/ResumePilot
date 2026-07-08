import { proxyBackendResponse } from "@/lib/backend";

export const dynamic = "force-dynamic";

interface ResumeRouteContext {
  params: Promise<{
    resumeId: string;
  }>;
}

export async function GET(request: Request, context: ResumeRouteContext) {
  const { resumeId } = await context.params;
  return proxyBackendResponse(`/resumes/${encodeURIComponent(resumeId)}`, undefined, {
    request
  });
}
