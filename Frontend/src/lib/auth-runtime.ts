export const ACTIVE_AUTH_PROVIDERS = ["local", "clerk", "trusted_headers"] as const;

export type ActiveAuthProvider = (typeof ACTIVE_AUTH_PROVIDERS)[number];
export type AuthProvider = ActiveAuthProvider | "invalid";

export interface RuntimeEnv {
  [key: string]: string | undefined;
}

export interface AuthRuntimeConfig {
  provider: AuthProvider;
  configuredProvider: string;
  isProductionRuntime: boolean;
  localAuthAllowedInProduction: boolean;
  isUsable: boolean;
  reason: string | null;
}

export function resolveAuthRuntimeConfig(env: RuntimeEnv = process.env): AuthRuntimeConfig {
  const configuredProvider = normalizeProvider(env.RESUMEPILOT_AUTH_PROVIDER);
  const provider = toAuthProvider(configuredProvider);
  const isProductionRuntime = isProductionAuthRuntime(env);
  const localAuthAllowedInProduction = isEnabled(
    env.RESUMEPILOT_ALLOW_LOCAL_AUTH_IN_PRODUCTION
  );
  const hasBackendSigningSecret = hasValue(env.AUTH_TRUSTED_PROXY_SECRET);

  if (!provider) {
    return unusableConfig({
      provider: "invalid",
      configuredProvider,
      isProductionRuntime,
      localAuthAllowedInProduction,
      reason: `Unsupported RESUMEPILOT_AUTH_PROVIDER "${configuredProvider}". Use local, clerk, or trusted_headers.`
    });
  }

  if (provider === "local") {
    if (isProductionRuntime && !localAuthAllowedInProduction) {
      return unusableConfig({
        provider,
        configuredProvider,
        isProductionRuntime,
        localAuthAllowedInProduction,
        reason:
          "Local auth is disabled in production. Use RESUMEPILOT_AUTH_PROVIDER=clerk or trusted_headers, or explicitly set RESUMEPILOT_ALLOW_LOCAL_AUTH_IN_PRODUCTION=true for a private stack."
      });
    }
    if (isProductionRuntime && !hasBackendSigningSecret) {
      return unusableConfig({
        provider,
        configuredProvider,
        isProductionRuntime,
        localAuthAllowedInProduction,
        reason:
          "AUTH_TRUSTED_PROXY_SECRET is required for production local auth so the dashboard can sign backend identity headers."
      });
    }
  }

  if (provider === "clerk") {
    if (!hasBackendSigningSecret) {
      return unusableConfig({
        provider,
        configuredProvider,
        isProductionRuntime,
        localAuthAllowedInProduction,
        reason:
          "AUTH_TRUSTED_PROXY_SECRET is required when Clerk auth is enabled so backend identity headers are signed."
      });
    }
    if (!hasValue(env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY) || !hasValue(env.CLERK_SECRET_KEY)) {
      return unusableConfig({
        provider,
        configuredProvider,
        isProductionRuntime,
        localAuthAllowedInProduction,
        reason:
          "Clerk auth is enabled but NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY and CLERK_SECRET_KEY are not both configured."
      });
    }
  }

  if (provider === "trusted_headers" && !hasBackendSigningSecret) {
    return unusableConfig({
      provider,
      configuredProvider,
      isProductionRuntime,
      localAuthAllowedInProduction,
      reason:
        "AUTH_TRUSTED_PROXY_SECRET is required when trusted header auth is enabled so backend identity headers are signed."
    });
  }

  return {
    provider,
    configuredProvider,
    isProductionRuntime,
    localAuthAllowedInProduction,
    isUsable: true,
    reason: null
  };
}

export function shouldUseClerkProvider(env: RuntimeEnv = process.env): boolean {
  return (
    normalizeProvider(env.RESUMEPILOT_AUTH_PROVIDER) === "clerk" &&
    hasValue(env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY)
  );
}

export function isClerkAuthReady(env: RuntimeEnv = process.env): boolean {
  const config = resolveAuthRuntimeConfig(env);
  return config.provider === "clerk" && config.isUsable;
}

export function isProductionAuthRuntime(env: RuntimeEnv = process.env): boolean {
  return env.NODE_ENV === "production" || env.VERCEL_ENV === "production";
}

function unusableConfig(config: Omit<AuthRuntimeConfig, "isUsable">): AuthRuntimeConfig {
  return {
    ...config,
    isUsable: false
  };
}

function normalizeProvider(value: string | undefined): string {
  return (value?.trim().toLowerCase() || "local").replace(/-/g, "_");
}

function toAuthProvider(value: string): ActiveAuthProvider | null {
  return ACTIVE_AUTH_PROVIDERS.find((provider) => provider === value) ?? null;
}

function hasValue(value: string | undefined): boolean {
  return Boolean(value?.trim());
}

function isEnabled(value: string | undefined): boolean {
  const normalized = value?.trim().toLowerCase();
  return normalized === "1" || normalized === "true" || normalized === "yes";
}
