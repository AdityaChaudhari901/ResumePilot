import type { Metadata } from "next";

import { WorkspaceRoute } from "@/features/dashboard/components/workspace-route";

export const metadata: Metadata = {
  title: "Applications"
};

export default function ApplicationsPage() {
  return <WorkspaceRoute view="applications" />;
}
