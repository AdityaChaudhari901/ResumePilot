import { redirect } from "next/navigation";

import {
  DashboardShell,
  type DashboardView
} from "@/features/dashboard/components/dashboard-shell";
import { getAuthSession } from "@/lib/auth";

interface WorkspaceRouteProps {
  initialApplicationId?: number;
  initialReportId?: number;
  view: DashboardView;
}

export async function WorkspaceRoute({
  initialApplicationId,
  initialReportId,
  view
}: WorkspaceRouteProps) {
  const session = await getAuthSession();
  if (!session.isAuthenticated) {
    redirect("/");
  }

  return (
    <DashboardShell
      initialApplicationId={initialApplicationId}
      initialAuthSession={session}
      initialReportId={initialReportId}
      view={view}
    />
  );
}
