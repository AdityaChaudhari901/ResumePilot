import { createGatewayUrl } from "@/lib/backend";
import { authFailureResponse, getAuthSession } from "@/lib/auth";
import {
  getObject,
  readJsonFile,
  resolveGatewayToken,
  resolveOpenClawPaths
} from "@/lib/openclaw";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

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

function providerHasModel(registry: unknown, provider: string, modelId: string): boolean {
  const registryObject = getObject(registry);
  const providers = getObject(registryObject?.providers);
  const providerConfig = getObject(providers?.[provider]);
  const models = providerConfig?.models;
  return Array.isArray(models)
    ? models.some((model) => getObject(model)?.id === modelId)
    : false;
}

function globalConfigHasModel(config: unknown, provider: string, modelId: string): boolean {
  const configObject = getObject(config);
  const models = getObject(configObject?.models);
  return providerHasModel(models, provider, modelId);
}

function sessionRegistryHasKey(registry: unknown, sessionKey: string): boolean {
  const registryObject = getObject(registry);
  return Boolean(registryObject?.[sessionKey]);
}

function buildGatewayPath(gatewayUrl: string, pathname: string): string {
  try {
    const url = new URL(gatewayUrl);
    url.pathname = pathname;
    return url.toString();
  } catch {
    return `${gatewayUrl.replace(/\/+$/, "")}${pathname}`;
  }
}

export async function GET(request: Request) {
  const session = await getAuthSession(request);
  if (!session.isAuthenticated) {
    return authFailureResponse(session);
  }

  const gatewayUrl = createGatewayUrl();
  const llmProvider = process.env.LLM_PROVIDER ?? "vertex";
  const provider = process.env.OPENCLAW_PROVIDER ?? (llmProvider === "vertex" ? "google-vertex" : llmProvider);
  const llmModel = process.env.LLM_MODEL ?? "gemini-3.5-flash";
  const modelReference = process.env.OPENCLAW_MODEL_REFERENCE ?? `${provider}/${llmModel}`;
  const googleCloudProject =
    process.env.VERTEX_PROJECT_ID ?? process.env.GOOGLE_CLOUD_PROJECT ?? process.env.GCLOUD_PROJECT;
  const googleCloudLocation =
    process.env.VERTEX_REGION ?? process.env.GOOGLE_CLOUD_LOCATION ?? process.env.GOOGLE_CLOUD_REGION;
  const gatewayProbe = await probeGateway(gatewayUrl);
  const modelId = modelReference.includes("/") ? modelReference.split("/", 2)[1] : llmModel;
  const paths = resolveOpenClawPaths();
  const [globalConfig, agentModels, sessions, gatewayToken] = await Promise.all([
    readJsonFile(paths.globalConfigPath),
    readJsonFile(paths.agentModelsPath),
    readJsonFile(paths.sessionsPath),
    resolveGatewayToken(paths)
  ]);
  const modelRegistered = globalConfigHasModel(globalConfig, provider, modelId);
  const agentModelRegistered = providerHasModel(agentModels, provider, modelId);
  const mainSessionRegistered = sessionRegistryHasKey(sessions, `agent:${paths.agentId}:${paths.agentId}`);
  const controlReady = gatewayProbe.reachable && modelRegistered && Boolean(googleCloudProject);

  return Response.json({
    llmProvider,
    llmModel,
    provider,
    modelReference,
    gatewayUrl,
    dashboardUrl: "/api/openclaw/control?view=overview",
    chatUrl: "/api/openclaw/control?view=chat",
    rawDashboardUrl: gatewayUrl,
    rawChatUrl: buildGatewayPath(gatewayUrl, "/chat"),
    webSocketUrl: toWebSocketUrl(gatewayUrl),
    gateway: {
      reachable: gatewayProbe.reachable,
      statusCode: gatewayProbe.statusCode,
      checkedAt: new Date().toISOString()
    },
    auth: {
      vertexAuth: "gcloud Application Default Credentials",
      hasGatewayToken: Boolean(gatewayToken),
      projectConfigured: Boolean(googleCloudProject),
      location: googleCloudLocation ?? "not set"
    },
    readiness: {
      modelRegistered,
      agentModelRegistered,
      mainSessionRegistered,
      dashboardLaunch: "Use Open Fresh Chat to open an authenticated local Control UI tab.",
      status: controlReady ? "ready" : "needs_setup"
    },
    commands: {
      configure: "./Ai services/openclaw/scripts/configure_vertex_gateway.sh",
      gateway: "./Ai services/openclaw/scripts/start_local_gateway.sh",
      dashboard: "openclaw dashboard",
      setModel: `openclaw models set ${modelReference}`
    }
  });
}
