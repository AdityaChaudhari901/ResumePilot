import type { Metadata } from "next";

import { WorkspaceRoute } from "@/features/dashboard/components/workspace-route";

export const metadata: Metadata = {
  title: "New application"
};

export default function NewApplicationPage() {
  return <WorkspaceRoute view="workflow" />;
}
