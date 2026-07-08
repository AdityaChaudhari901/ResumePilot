import { createGatewayUrl } from "@/lib/backend";

export const dynamic = "force-dynamic";

function toWebSocketUrl(gatewayUrl: string): string {
  return gatewayUrl.replace(/^https:/, "wss:").replace(/^http:/, "ws:").replace(/\/+$/, "");
}

export async function GET() {
  const gatewayUrl = createGatewayUrl();
  const provider = process.env.OPENCLAW_PROVIDER ?? "google-vertex";
  const modelReference = process.env.OPENCLAW_MODEL_REFERENCE ?? `${provider}/gemini-3.5-flash`;
  const googleCloudProject = process.env.GOOGLE_CLOUD_PROJECT ?? process.env.GCLOUD_PROJECT;
  const googleCloudLocation = process.env.GOOGLE_CLOUD_LOCATION ?? process.env.GOOGLE_CLOUD_REGION;

  return Response.json({
    provider,
    modelReference,
    gatewayUrl,
    dashboardUrl: gatewayUrl,
    webSocketUrl: toWebSocketUrl(gatewayUrl),
    auth: {
      vertexAuth: "gcloud Application Default Credentials",
      hasGatewayToken: Boolean(process.env.OPENCLAW_GATEWAY_TOKEN),
      projectConfigured: Boolean(googleCloudProject),
      location: googleCloudLocation ?? "not set"
    },
    commands: {
      gateway: "openclaw gateway run --bind loopback",
      dashboard: "openclaw dashboard",
      setModel: `openclaw models set ${modelReference}`
    }
  });
}
