import { SignUp } from "@clerk/nextjs";
import { redirect } from "next/navigation";

export default function SignUpPage() {
  if (process.env.RESUMEPILOT_AUTH_PROVIDER !== "clerk") {
    redirect("/");
  }

  return (
    <main className="flex min-h-dvh items-center justify-center px-4 py-8">
      <SignUp path="/sign-up" routing="path" signInUrl="/sign-in" />
    </main>
  );
}
