import "server-only";

import { createHmac } from "node:crypto";

export type AuthProvider = "local" | "clerk" | "trusted_headers";

export interface AuthenticatedSession {
  isAuthenticated: true;
  provider: AuthProvider;
  externalId: string;
  email: string | null;
  displayName: string | null;
}

export interface AnonymousSession {
  isAuthenticated: false;
  provider: AuthProvider;
  reason: string;
}

export type AuthSession = AuthenticatedSession | AnonymousSession;

const USER_ID_HEADER = "X-ResumePilot-User";
const USER_EMAIL_HEADER = "X-ResumePilot-Email";
const USER_NAME_HEADER = "X-ResumePilot-Name";
const AUTH_TIMESTAMP_HEADER = "x-resumepilot-auth-timestamp";
const AUTH_SIGNATURE_HEADER = "x-resumepilot-auth-signature";

export async function getAuthSession(request?: Request): Promise<AuthSession> {
  const provider = getAuthProvider();
  if (provider === "local") {
    return localSession();
  }
  if (provider === "trusted_headers") {
    return trustedHeaderSession(request);
  }
  return clerkSession();
}

export function authFailureResponse(session: AnonymousSession): Response {
  return Response.json(
    {
      detail: session.reason,
      provider: session.provider
    },
    {
      status: 401,
      headers: {
        "Cache-Control": "no-store"
      }
    }
  );
}

export function signedBackendIdentityHeaders(session: AuthenticatedSession): Headers {
  const headers = new Headers({
    [USER_ID_HEADER]: session.externalId
  });
  if (session.email) {
    headers.set(USER_EMAIL_HEADER, session.email);
  }
  if (session.displayName) {
    headers.set(USER_NAME_HEADER, session.displayName);
  }

  const secret = process.env.AUTH_TRUSTED_PROXY_SECRET?.trim();
  if (!secret) {
    if (session.provider === "local") {
      return headers;
    }
    throw new Error("AUTH_TRUSTED_PROXY_SECRET is required for authenticated backend proxy calls.");
  }

  const timestamp = String(Math.floor(Date.now() / 1000));
  headers.set(AUTH_TIMESTAMP_HEADER, timestamp);
  headers.set(
    AUTH_SIGNATURE_HEADER,
    signIdentity({
      secret,
      externalId: session.externalId,
      email: session.email,
      displayName: session.displayName,
      timestamp
    })
  );
  return headers;
}

function getAuthProvider(): AuthProvider {
  const configured = (process.env.RESUMEPILOT_AUTH_PROVIDER ?? "local").trim().toLowerCase();
  if (configured === "local" || configured === "clerk" || configured === "trusted_headers") {
    return configured;
  }
  return "local";
}

function localSession(): AuthenticatedSession {
  const externalId = process.env.DEV_USER_EXTERNAL_ID?.trim() || "local-dev-user";
  const email = normalizeOptional(process.env.DEV_USER_EMAIL);
  const displayName = normalizeOptional(process.env.DEV_USER_DISPLAY_NAME) ?? "Local Developer";
  return {
    isAuthenticated: true,
    provider: "local",
    externalId,
    email,
    displayName
  };
}

function trustedHeaderSession(request: Request | undefined): AuthSession {
  if (!request) {
    return {
      isAuthenticated: false,
      provider: "trusted_headers",
      reason: "Trusted identity headers are unavailable for this request."
    };
  }

  const externalId = normalizeOptional(request.headers.get("x-resumepilot-auth-user"));
  if (!externalId) {
    return {
      isAuthenticated: false,
      provider: "trusted_headers",
      reason: "Missing authenticated user context."
    };
  }

  return {
    isAuthenticated: true,
    provider: "trusted_headers",
    externalId,
    email: normalizeOptional(request.headers.get("x-resumepilot-auth-email")),
    displayName: normalizeOptional(request.headers.get("x-resumepilot-auth-name"))
  };
}

async function clerkSession(): Promise<AuthSession> {
  const { auth, currentUser } = await import("@clerk/nextjs/server");
  const authState = await auth();
  if (!authState.isAuthenticated || !authState.userId) {
    return {
      isAuthenticated: false,
      provider: "clerk",
      reason: "Sign in to use ResumePilot."
    };
  }

  const user = await currentUser();
  const email =
    user?.primaryEmailAddress?.emailAddress ??
    user?.emailAddresses[0]?.emailAddress ??
    null;
  const fullName = [user?.firstName, user?.lastName].filter(Boolean).join(" ");
  const displayName =
    user?.fullName ??
    (fullName || email || authState.userId);

  return {
    isAuthenticated: true,
    provider: "clerk",
    externalId: `clerk:${authState.userId}`,
    email,
    displayName
  };
}

function signIdentity({
  secret,
  externalId,
  email,
  displayName,
  timestamp
}: {
  secret: string;
  externalId: string;
  email: string | null;
  displayName: string | null;
  timestamp: string;
}): string {
  return createHmac("sha256", secret)
    .update([externalId, email ?? "", displayName ?? "", timestamp].join("\n"), "utf8")
    .digest("hex");
}

function normalizeOptional(value: string | null | undefined): string | null {
  if (!value) {
    return null;
  }
  const normalized = value.trim();
  return normalized || null;
}
