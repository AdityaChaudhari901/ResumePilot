import { SignUp } from "@clerk/nextjs";
import { redirect } from "next/navigation";

import { isClerkAuthReady } from "@/lib/auth-runtime";

export default function SignUpPage() {
  if (!isClerkAuthReady(process.env)) {
    redirect("/");
  }

  return (
    <main className="flex min-h-dvh items-center justify-center px-4 py-8">
      <SignUp path="/sign-up" routing="path" signInUrl="/sign-in" />
    </main>
  );
}
