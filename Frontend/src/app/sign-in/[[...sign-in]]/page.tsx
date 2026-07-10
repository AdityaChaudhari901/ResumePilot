import { SignIn } from "@clerk/nextjs";
import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { AuthShell } from "@/components/auth-shell";
import { isClerkAuthReady } from "@/lib/auth-runtime";
import { clerkAppearance } from "@/lib/clerk-appearance";

export const metadata: Metadata = {
  title: "Sign in"
};

export default function SignInPage() {
  if (!isClerkAuthReady(process.env)) {
    redirect("/");
  }

  return (
    <AuthShell mode="sign-in">
      <SignIn
        appearance={clerkAppearance}
        path="/sign-in"
        routing="path"
        signUpUrl="/sign-up"
      />
    </AuthShell>
  );
}
