import { AppShell } from "@/components/app-shell";
import { StatePanel } from "@/components/state-panel";

export default function ScanLoading() {
  return (
    <AppShell>
      <StatePanel
        kind="loading"
        title="Loading scan"
        description="Fetching findings, source locations, and remediation guidance."
      />
    </AppShell>
  );
}
