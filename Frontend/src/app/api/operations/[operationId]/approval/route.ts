import { proxyBackendResponse } from "@/lib/backend";

export const dynamic = "force-dynamic";

export async function POST(
  request: Request,
  context: { params: Promise<{ operationId: string }> }
) {
  const { operationId } = await context.params;
  const body = await request.text();
  const idempotencyKey = request.headers.get("idempotency-key")?.trim();

  if (!idempotencyKey) {
    return Response.json(
      { detail: "Idempotency-Key is required for an approval decision." },
      { status: 400 }
    );
  }

  return proxyBackendResponse(
    `/operations/${encodeURIComponent(operationId)}/approval`,
    {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "idempotency-key": idempotencyKey
      },
      body
    },
    { request }
  );
}
