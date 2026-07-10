import { proxyBackendResponse } from "@/lib/backend";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  return proxyBackendResponse(
    "/operations?limit=20",
    { method: "GET" },
    { request }
  );
}
