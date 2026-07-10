import { proxyBackendResponse } from "@/lib/backend";

export const dynamic = "force-dynamic";

interface RouteContext {
  params: Promise<{
    applicationId: string;
    itemId: string;
  }>;
}

export async function PATCH(request: Request, context: RouteContext) {
  const { applicationId, itemId } = await context.params;
  const body = await request.text();
  return proxyBackendResponse(
    `/applications/${encodeURIComponent(applicationId)}/tailored-resume/items/${encodeURIComponent(
      itemId
    )}`,
    {
      method: "PATCH",
      headers: {
        "content-type": "application/json"
      },
      body
    },
    {
      request
    }
  );
}
