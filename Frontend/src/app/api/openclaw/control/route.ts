import { NextRequest } from "next/server";

import {
  buildOpenClawControlUrl,
  isLoopbackGatewayUrl,
  resolveGatewayToken
} from "@/lib/openclaw";
import { authFailureResponse, getAuthSession } from "@/lib/auth";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET(request: NextRequest) {
  const session = await getAuthSession(request);
  if (!session.isAuthenticated) {
    return authFailureResponse(session);
  }

  if (!isLoopbackGatewayUrl() && process.env.OPENCLAW_ALLOW_TOKEN_REDIRECT !== "true") {
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
