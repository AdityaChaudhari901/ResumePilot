import { SignIn } from "@clerk/nextjs";
import { redirect } from "next/navigation";

import { isClerkAuthReady } from "@/lib/auth-runtime";

export default function SignInPage() {
  if (!isClerkAuthReady(process.env)) {
    redirect("/");
  }

  return (
    <main className="flex min-h-dvh items-center justify-center px-4 py-8">
      <SignIn path="/sign-in" routing="path" signUpUrl="/sign-up" />
    </main>
  );
}
