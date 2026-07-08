const DEFAULT_BACKEND_BASE_URL = "http://127.0.0.1:8000";

export function getBackendBaseUrl(): string {
  const configuredUrl = process.env.RESUMEPILOT_API_BASE_URL ?? DEFAULT_BACKEND_BASE_URL;
  return configuredUrl.replace(/\/+$/, "");
}

export async function proxyBackendResponse(path: string, init?: RequestInit): Promise<Response> {
  const backendResponse = await fetch(`${getBackendBaseUrl()}${path}`, {
    ...init,
    cache: "no-store"
  });
  const contentType = backendResponse.headers.get("content-type") ?? "application/json";
  const responseBody = await backendResponse.arrayBuffer();

  return new Response(responseBody, {
    status: backendResponse.status,
    headers: {
      "content-type": contentType
    }
  });
}

export function createGatewayUrl(): string {
  return process.env.OPENCLAW_GATEWAY_URL ?? "http://127.0.0.1:18789/";
}
