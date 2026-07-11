import type { Metadata } from "next";

import { WorkspaceRoute } from "@/features/dashboard/components/workspace-route";

export const metadata: Metadata = {
  title: "Reports"
};

export default function ReportsPage() {
  return <WorkspaceRoute view="reports" />;
}
