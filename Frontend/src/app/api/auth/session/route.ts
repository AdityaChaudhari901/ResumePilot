import { getAuthSession } from "@/lib/auth";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET(request: Request) {
  const session = await getAuthSession(request);
  return Response.json(session, {
    headers: {
      "Cache-Control": "no-store"
    }
  });
}
