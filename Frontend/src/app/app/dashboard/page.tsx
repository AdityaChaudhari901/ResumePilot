import type { Metadata } from "next";

import { WorkspaceRoute } from "@/features/dashboard/components/workspace-route";

export const metadata: Metadata = {
  title: "Dashboard"
};

export default function DashboardPage() {
  return <WorkspaceRoute view="overview" />;
}
