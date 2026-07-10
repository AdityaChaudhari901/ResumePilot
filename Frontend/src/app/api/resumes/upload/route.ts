import { proxyBackendResponse } from "@/lib/backend";

export const dynamic = "force-dynamic";
const MAX_UPLOAD_REQUEST_BYTES = 6 * 1024 * 1024;

export async function POST(request: Request) {
  const contentLength = request.headers.get("content-length");
  if (contentLength && Number(contentLength) > MAX_UPLOAD_REQUEST_BYTES) {
    return Response.json(
      { detail: "Resume upload exceeds the gateway processing limit." },
      { status: 413 }
    );
  }

  const contentType = request.headers.get("content-type");
  const upstreamRequest: RequestInit & { duplex: "half" } = {
    method: "POST",
    body: request.body,
    duplex: "half",
    headers: contentType ? { "content-type": contentType } : undefined
  };
  return proxyBackendResponse("/resumes/upload", upstreamRequest, { request });
}
