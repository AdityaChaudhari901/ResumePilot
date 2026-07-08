import { proxyBackendResponse } from "@/lib/backend";

export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  const body = await request.text();
  return proxyBackendResponse("/jobs/analyze", {
    method: "POST",
    headers: {
      "content-type": "application/json"
    },
    body
  }, {
    request
  });
}
