import { proxyBackendResponse } from "@/lib/backend";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const requestUrl = new URL(request.url);
  const limit = requestUrl.searchParams.get("limit") ?? "20";
  return proxyBackendResponse(`/reports?limit=${encodeURIComponent(limit)}`, undefined, {
    request
  });
}
