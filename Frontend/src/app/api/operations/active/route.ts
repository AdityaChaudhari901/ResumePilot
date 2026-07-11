import { parsePositiveSafeInteger } from "@/features/dashboard/utils/route-params";
import { proxyBackendResponse } from "@/lib/backend";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const requestUrl = new URL(request.url);
  const rawApplicationId = requestUrl.searchParams.get("application_id");
  const applicationId = rawApplicationId
    ? parsePositiveSafeInteger(rawApplicationId)
    : null;
  if (rawApplicationId && applicationId === null) {
    return Response.json(
      { detail: "application_id must be a positive safe integer." },
      {
        status: 400,
        headers: {
          "Cache-Control": "private, no-store, max-age=0",
          "X-Content-Type-Options": "nosniff"
        }
      }
    );
  }

  const query = new URLSearchParams({ kind: "analysis" });
  if (applicationId !== null) {
    query.set("application_id", String(applicationId));
  }
  return proxyBackendResponse(
    `/operations/active?${query.toString()}`,
    { method: "GET" },
    { request }
  );
}
