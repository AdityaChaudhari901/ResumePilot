import {
  authFailureResponse,
  getAuthSession,
  signedBackendIdentityHeaders
} from "@/lib/auth";

const DEFAULT_BACKEND_BASE_URL = "http://127.0.0.1:8000";
const PRIVATE_PROXY_CACHE_CONTROL = "private, no-store, max-age=0";
const AUTHENTICATED_RESPONSE_VARY = [
  "Authorization",
  "Cookie",
  "X-ResumePilot-Auth-User",
  "X-ResumePilot-Auth-Email",
  "X-ResumePilot-Auth-Name"
].join(", ");

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
  const requestMethod = init?.method ?? options.request?.method;
  const requestBody =
    init?.body ??
    (options.request && !["GET", "HEAD"].includes(options.request.method)
      ? await options.request.arrayBuffer()
      : undefined);

  if (authRequired) {
    const session = await getAuthSession(options.request);
    if (!session.isAuthenticated) {
      return authFailureResponse(session);
    }
    try {
      signedBackendIdentityHeaders(session, {
        method: requestMethod ?? "GET",
        path: path.split("?", 1)[0]
      }).forEach((value, key) => {
        requestHeaders.set(key, value);
      });
    } catch {
      return Response.json(
        {
          detail: "Authenticated backend proxy is not configured."
        },
        {
          status: 500,
          headers: {
            "Cache-Control": PRIVATE_PROXY_CACHE_CONTROL,
            "Vary": AUTHENTICATED_RESPONSE_VARY,
            "X-Content-Type-Options": "nosniff"
          }
        }
      );
    }
  }

  const backendResponse = await fetch(`${getBackendBaseUrl()}${path}`, {
    ...init,
    method: requestMethod,
    body: requestBody,
    headers: requestHeaders,
    cache: "no-store"
  });
  const contentType = backendResponse.headers.get("content-type") ?? "application/json";
  const contentDisposition = backendResponse.headers.get("content-disposition");
  const responseBody = await backendResponse.arrayBuffer();
  const headers = new Headers({
    "Cache-Control": PRIVATE_PROXY_CACHE_CONTROL,
    "content-type": contentType,
    "Vary": AUTHENTICATED_RESPONSE_VARY,
    "X-Content-Type-Options": "nosniff"
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
