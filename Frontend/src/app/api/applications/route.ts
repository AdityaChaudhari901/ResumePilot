import { proxyBackendResponse } from "@/lib/backend";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const requestUrl = new URL(request.url);
  return proxyBackendResponse(`/applications${requestUrl.search}`, undefined, { request });
}

export async function POST(request: Request) {
  const body = await request.text();
  return proxyBackendResponse(
    "/applications",
    {
      method: "POST",
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
