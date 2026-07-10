import { proxyBackendResponse } from "@/lib/backend";

export const dynamic = "force-dynamic";

export async function POST(
  request: Request,
  context: { params: Promise<{ operationId: string }> }
) {
  const { operationId } = await context.params;
  return proxyBackendResponse(
    `/operations/${encodeURIComponent(operationId)}/cancel`,
    { method: "POST" },
    { request }
  );
}
