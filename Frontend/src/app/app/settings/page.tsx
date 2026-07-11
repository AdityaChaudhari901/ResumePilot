import type { Metadata } from "next";

import { WorkspaceRoute } from "@/features/dashboard/components/workspace-route";

export const metadata: Metadata = {
  title: "Settings"
};

export default function SettingsPage() {
  return <WorkspaceRoute view="settings" />;
}
