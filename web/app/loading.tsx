import { AppShell } from "@/components/app-shell";
import { StatePanel } from "@/components/state-panel";

export default function Loading() {
  return (
    <AppShell>
      <StatePanel
        kind="loading"
        title="Loading dashboard"
        description="Fetching repositories and recent scan activity."
      />
    </AppShell>
  );
}
