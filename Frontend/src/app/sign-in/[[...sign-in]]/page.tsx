import { SignIn } from "@clerk/nextjs";
import { redirect } from "next/navigation";

export default function SignInPage() {
  if (process.env.RESUMEPILOT_AUTH_PROVIDER !== "clerk") {
    redirect("/");
  }

  return (
    <main className="flex min-h-dvh items-center justify-center px-4 py-8">
      <SignIn path="/sign-in" routing="path" signUpUrl="/sign-up" />
    </main>
  );
}
