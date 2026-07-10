import { SignUp } from "@clerk/nextjs";
import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { AuthShell } from "@/components/auth-shell";
import { isClerkAuthReady } from "@/lib/auth-runtime";
import { clerkAppearance } from "@/lib/clerk-appearance";

export const metadata: Metadata = {
  title: "Create account"
};

export default function SignUpPage() {
  if (!isClerkAuthReady(process.env)) {
    redirect("/");
  }

  return (
    <AuthShell mode="sign-up">
      <SignUp
        appearance={clerkAppearance}
        path="/sign-up"
        routing="path"
        signInUrl="/sign-in"
      />
    </AuthShell>
  );
}
