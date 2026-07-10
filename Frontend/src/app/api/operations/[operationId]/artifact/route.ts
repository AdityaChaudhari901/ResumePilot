import { proxyBackendResponse } from "@/lib/backend";

export const dynamic = "force-dynamic";

export async function GET(
  request: Request,
  context: { params: Promise<{ operationId: string }> }
) {
  const { operationId } = await context.params;
  return proxyBackendResponse(
    `/operations/${encodeURIComponent(operationId)}/artifact`,
    { method: "GET" },
    { request, timeoutMs: 30_000 }
  );
}
