import { clerkMiddleware } from "@clerk/nextjs/server";
import { NextResponse, type NextFetchEvent, type NextRequest } from "next/server";

import { shouldUseClerkProvider } from "@/lib/auth-runtime";

const clerkProxy = clerkMiddleware();

export default function proxy(request: NextRequest, event: NextFetchEvent) {
  if (shouldUseClerkProvider(process.env)) {
    return clerkProxy(request, event);
  }
  return NextResponse.next();
}

export const config = {
  matcher: [
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
    "/(api)(.*)",
    "/__clerk/(.*)"
  ]
};
