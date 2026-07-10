import { NextRequest } from "next/server";

import {
  buildOpenClawControlUrl,
  isLoopbackGatewayUrl,
  resolveGatewayToken
} from "@/lib/openclaw";
import { authFailureResponse, getAuthSession } from "@/lib/auth";
import { resolveAuthRuntimeConfig } from "@/lib/auth-runtime";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET(request: NextRequest) {
  const session = await getAuthSession(request);
  if (!session.isAuthenticated) {
    return authFailureResponse(session);
  }

  const authRuntime = resolveAuthRuntimeConfig(process.env);
  if (authRuntime.provider !== "local" || !authRuntime.isUsable) {
    return Response.json(
      { detail: "OpenClaw Control is available only in private local auth mode." },
      {
        status: 403,
        headers: {
          "Cache-Control": "no-store"
        }
      }
    );
  }

  if (!isLoopbackGatewayUrl()) {
    return Response.json(
      { detail: "OpenClaw token redirect is only enabled for loopback gateways." },
      {
        status: 403,
        headers: {
          "Cache-Control": "no-store"
        }
      }
    );
  }

  const token = await resolveGatewayToken();
  if (!token) {
    return Response.json(
      {
        detail:
          "OpenClaw gateway token is not available to the ResumePilot dashboard server."
      },
      {
        status: 503,
        headers: {
          "Cache-Control": "no-store"
        }
      }
    );
  }

  const view = request.nextUrl.searchParams.get("view") === "overview" ? "overview" : "chat";
  const sessionKey = request.nextUrl.searchParams.get("session") ?? undefined;
  const location = buildOpenClawControlUrl({ token, view, sessionKey });

  return new Response(null, {
    status: 307,
    headers: {
      "Cache-Control": "no-store",
      Location: location
    }
  });
}
