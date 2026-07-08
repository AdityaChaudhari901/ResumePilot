import { getBackendBaseUrl } from "@/lib/backend";

export const dynamic = "force-dynamic";

interface BackendHealthPayload {
  status?: string;
  app?: string;
  environment?: string;
}

export async function GET() {
  const startedAt = Date.now();
  const backendBaseUrl = getBackendBaseUrl();

  try {
    const response = await fetch(`${backendBaseUrl}/health`, { cache: "no-store" });
    const latencyMs = Date.now() - startedAt;

    if (!response.ok) {
      return Response.json({
        status: "degraded",
        backendReachable: true,
        backendBaseUrl,
        latencyMs,
        message: `Backend returned HTTP ${response.status}`
      });
    }

    const backend = (await response.json()) as BackendHealthPayload;
    return Response.json({
      status: "ok",
      backendReachable: true,
      backendBaseUrl,
      latencyMs,
      backend
    });
  } catch {
    return Response.json({
      status: "offline",
      backendReachable: false,
      backendBaseUrl,
      latencyMs: Date.now() - startedAt,
      message: "FastAPI backend is not reachable"
    });
  }
}
