import { AuthRequiredPanel } from "@/features/dashboard/components/auth-required-panel";
import { DashboardShell } from "@/features/dashboard/components/dashboard-shell";
import { getAuthSession } from "@/lib/auth";

export default async function Page() {
  const session = await getAuthSession();
  if (!session.isAuthenticated) {
    return <AuthRequiredPanel session={session} />;
  }
  return <DashboardShell initialAuthSession={session} />;
}
