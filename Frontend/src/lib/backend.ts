import {
  authFailureResponse,
  getAuthSession,
  signedBackendIdentityHeaders
} from "@/lib/auth";

const DEFAULT_BACKEND_BASE_URL = "http://127.0.0.1:8000";

export function getBackendBaseUrl(): string {
  const configuredUrl = process.env.RESUMEPILOT_API_BASE_URL ?? DEFAULT_BACKEND_BASE_URL;
  return configuredUrl.replace(/\/+$/, "");
}

interface ProxyBackendOptions {
  authRequired?: boolean;
  request?: Request;
}

export async function proxyBackendResponse(
  path: string,
  init?: RequestInit,
  options: ProxyBackendOptions = {}
): Promise<Response> {
  const requestHeaders = new Headers(init?.headers);
  const authRequired = options.authRequired ?? true;

  if (authRequired) {
    const session = await getAuthSession(options.request);
    if (!session.isAuthenticated) {
      return authFailureResponse(session);
    }
    try {
      signedBackendIdentityHeaders(session).forEach((value, key) => {
        requestHeaders.set(key, value);
      });
    } catch (error) {
      return Response.json(
        {
          detail:
            error instanceof Error
              ? error.message
              : "Authenticated backend proxy is not configured."
        },
        { status: 500 }
      );
    }
  }

  const backendResponse = await fetch(`${getBackendBaseUrl()}${path}`, {
    ...init,
    headers: requestHeaders,
    cache: "no-store"
  });
  const contentType = backendResponse.headers.get("content-type") ?? "application/json";
  const contentDisposition = backendResponse.headers.get("content-disposition");
  const responseBody = await backendResponse.arrayBuffer();
  const headers = new Headers({
    "content-type": contentType
  });

  if (contentDisposition) {
    headers.set("content-disposition", contentDisposition);
  }

  return new Response(responseBody, {
    status: backendResponse.status,
    headers
  });
}

export function createGatewayUrl(): string {
  return process.env.OPENCLAW_GATEWAY_URL ?? "http://127.0.0.1:18789/";
}
