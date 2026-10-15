import { AppShell } from "@/components/app-shell";
import { StatePanel } from "@/components/state-panel";

export default function RepositoryLoading() {
  return (
    <AppShell>
      <StatePanel
        kind="loading"
        title="Loading repository"
        description="Fetching risk trends, scan history, and findings."
      />
    </AppShell>
  );
}
