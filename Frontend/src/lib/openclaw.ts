import { readFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";

import { createGatewayUrl } from "@/lib/backend";

export interface OpenClawPaths {
  agentId: string;
  agentModelsPath: string;
  globalConfigPath: string;
  localEnvPath: string;
  openclawHome: string;
  sessionsPath: string;
}

export function resolveOpenClawPaths(): OpenClawPaths {
  const openclawHome = process.env.OPENCLAW_HOME ?? path.join(os.homedir(), ".openclaw");
  const agentId = process.env.OPENCLAW_AGENT_ID ?? "main";
  const repoRoot = path.resolve(process.cwd(), "..");

  return {
    agentId,
    openclawHome,
    globalConfigPath: process.env.OPENCLAW_CONFIG_FILE ?? path.join(openclawHome, "openclaw.json"),
    agentModelsPath:
      process.env.OPENCLAW_AGENT_MODELS_FILE ??
      path.join(openclawHome, "agents", agentId, "agent", "models.json"),
    sessionsPath: path.join(openclawHome, "agents", agentId, "sessions", "sessions.json"),
    localEnvPath:
      process.env.OPENCLAW_LOCAL_ENV_FILE ??
      path.join(repoRoot, "Ai services", "openclaw", ".local", "openclaw-gateway.env")
  };
}

export async function readJsonFile(filePath: string): Promise<unknown | null> {
  try {
    return JSON.parse(await readFile(filePath, "utf-8"));
  } catch {
    return null;
  }
}

export function getObject(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

export async function resolveGatewayToken(paths = resolveOpenClawPaths()): Promise<string | null> {
  const configToken = await readGatewayTokenFromConfig(paths.globalConfigPath);
  if (configToken) {
    return configToken;
  }

  const envToken = process.env.OPENCLAW_GATEWAY_TOKEN?.trim();
  if (envToken) {
    return envToken;
  }

  const localEnvToken = await readGatewayTokenFromEnvFile(paths.localEnvPath);
  if (localEnvToken) {
    return localEnvToken;
  }

  return null;
}

async function readGatewayTokenFromConfig(filePath: string): Promise<string | null> {
  const config = getObject(await readJsonFile(filePath));
  const gateway = getObject(config?.gateway);
  const auth = getObject(gateway?.auth);
  const token = auth?.token;
  return typeof token === "string" && token.trim() ? token.trim() : null;
}

export async function readGatewayTokenFromEnvFile(filePath: string): Promise<string | null> {
  let body = "";
  try {
    body = await readFile(filePath, "utf-8");
  } catch {
    return null;
  }

  for (const line of body.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) {
      continue;
    }
    const [key, ...valueParts] = trimmed.split("=");
    if (key !== "OPENCLAW_GATEWAY_TOKEN") {
      continue;
    }
    return normalizeEnvValue(valueParts.join("="));
  }
  return null;
}

function normalizeEnvValue(rawValue: string): string | null {
  const value = rawValue.trim();
  if (!value) {
    return null;
  }
  if (
    (value.startsWith('"') && value.endsWith('"')) ||
    (value.startsWith("'") && value.endsWith("'"))
  ) {
    return value.slice(1, -1);
  }
  return value.replace(/\\([\\\s"'$`])/g, "$1");
}

export function buildOpenClawControlUrl(params: {
  token: string;
  view: "chat" | "overview";
  sessionKey?: string;
}): string {
  const gatewayUrl = createGatewayUrl();
  const url = new URL(gatewayUrl);

  if (params.view === "chat") {
    url.pathname = "/chat";
    url.searchParams.set("session", params.sessionKey ?? "agent:main:main");
  } else {
    url.pathname = "/";
    url.searchParams.delete("session");
  }

  url.searchParams.set("token", params.token);
  return url.toString();
}

export function isLoopbackGatewayUrl(): boolean {
  try {
    const hostname = new URL(createGatewayUrl()).hostname;
    return hostname === "localhost" || hostname === "127.0.0.1" || hostname === "::1";
  } catch {
    return false;
  }
}
