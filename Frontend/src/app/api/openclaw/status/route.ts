import { createGatewayUrl } from "@/lib/backend";

export const dynamic = "force-dynamic";

function toWebSocketUrl(gatewayUrl: string): string {
  return gatewayUrl.replace(/^https:/, "wss:").replace(/^http:/, "ws:").replace(/\/+$/, "");
}

async function probeGateway(gatewayUrl: string): Promise<{ reachable: boolean; statusCode: number | null }> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 1_500);

  try {
    const response = await fetch(gatewayUrl, {
      cache: "no-store",
      signal: controller.signal
    });

    return {
      reachable: response.ok || response.status === 401 || response.status === 403,
      statusCode: response.status
    };
  } catch {
    return {
      reachable: false,
      statusCode: null
    };
  } finally {
    clearTimeout(timeout);
  }
}

export async function GET() {
  const gatewayUrl = createGatewayUrl();
  const provider = process.env.OPENCLAW_PROVIDER ?? "google-vertex";
  const modelReference = process.env.OPENCLAW_MODEL_REFERENCE ?? `${provider}/gemini-2.5-flash`;
  const googleCloudProject = process.env.GOOGLE_CLOUD_PROJECT ?? process.env.GCLOUD_PROJECT;
  const googleCloudLocation = process.env.GOOGLE_CLOUD_LOCATION ?? process.env.GOOGLE_CLOUD_REGION;
  const gatewayProbe = await probeGateway(gatewayUrl);

  return Response.json({
    provider,
    modelReference,
    gatewayUrl,
    dashboardUrl: gatewayUrl,
    webSocketUrl: toWebSocketUrl(gatewayUrl),
    gateway: {
      reachable: gatewayProbe.reachable,
      statusCode: gatewayProbe.statusCode,
      checkedAt: new Date().toISOString()
    },
    auth: {
      vertexAuth: "gcloud Application Default Credentials",
      hasGatewayToken: Boolean(process.env.OPENCLAW_GATEWAY_TOKEN),
      projectConfigured: Boolean(googleCloudProject),
      location: googleCloudLocation ?? "not set"
    },
    commands: {
      configure: "./Ai services/openclaw/scripts/configure_vertex_gateway.sh",
      gateway: "./Ai services/openclaw/scripts/start_local_gateway.sh",
      dashboard: "openclaw dashboard",
      setModel: `openclaw models set ${modelReference}`
    }
  });
}
