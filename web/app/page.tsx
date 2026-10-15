import { ApiState } from "@/components/api-state";
import { AppShell } from "@/components/app-shell";
import { RepositoryCard } from "@/components/repository-card";
import { StatePanel } from "@/components/state-panel";
import { getRepositories, loadApi } from "@/lib/api";

export const metadata = { title: "Repositories" };

export default async function RepositoriesPage() {
  const result = await loadApi(() => getRepositories());

  return (
    <AppShell
      eyebrow="Workspace overview"
      title="Repositories"
      description="Review scan health, finding volume, and risk trends across your connected codebases."
    >
      {result.status === "error" ? (
        <ApiState error={result.error} resource="repositories" />
      ) : result.data.items.length === 0 ? (
        <StatePanel
          kind="empty"
          title="No repositories connected"
          description="Repositories will appear here after the first authorized scan is ingested."
        />
      ) : (
        <>
          <div className="summary-row">
            <div>
              <p className="section-kicker">Connected repositories</p>
              <p className="summary-copy">
                {result.data.total} {result.data.total === 1 ? "repository" : "repositories"} in this workspace
              </p>
            </div>
            <span className="muted-label">Updated from AgentGuard API</span>
          </div>
          <div className="repository-grid">
            {result.data.items.map((repository) => (
              <RepositoryCard key={repository.id} repository={repository} />
            ))}
          </div>
        </>
      )}
    </AppShell>
  );
}
