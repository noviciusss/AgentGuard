import Link from "next/link";
import { ApiState } from "@/components/api-state";
import { AppShell } from "@/components/app-shell";
import { FindingList } from "@/components/finding-list";
import { MetricCard } from "@/components/metric-card";
import { RiskTrend } from "@/components/risk-trend";
import { ScanTable } from "@/components/scan-table";
import { StatePanel } from "@/components/state-panel";
import { getRepository, loadApi } from "@/lib/api";

interface RepositoryPageProps {
  params: { repositoryId: string };
}

export const dynamic = "force-dynamic";

const formatDate = (value: string | null): string => {
  if (!value) return "No scan yet";
  return new Intl.DateTimeFormat("en", { dateStyle: "medium" }).format(new Date(value));
};

export function generateMetadata() {
  return { title: "Repository" };
}

export default async function RepositoryPage({ params }: RepositoryPageProps) {
  const result = await loadApi(() => getRepository(params.repositoryId));

  if (result.status === "error") {
    return (
      <AppShell>
        <ApiState error={result.error} resource="this repository" />
      </AppShell>
    );
  }

  const repository = result.data;
  const latestScan = repository.latestScan;

  return (
    <AppShell
      eyebrow="Repository detail"
      title={repository.fullName}
      description={`${repository.provider} · ${repository.defaultBranch ?? "default branch unavailable"}`}
    >
      <div className="breadcrumb-row">
        <Link className="back-link" href="/">
          ← All repositories
        </Link>
        {latestScan ? <span>Last scan {formatDate(latestScan.createdAt)}</span> : null}
      </div>

      <div className="metric-grid">
        <MetricCard
          label="Open findings"
          value={repository.findingCount}
          detail="Across the latest repository state"
          tone={repository.findingCount > 0 ? "warning" : "positive"}
        />
        <MetricCard
          label="Risk score"
          value={repository.riskScore === null ? "—" : `${repository.riskScore}/100`}
          detail="Calculated by the API"
          tone={repository.riskScore !== null && repository.riskScore >= 70 ? "danger" : "neutral"}
        />
        <MetricCard
          label="Scans recorded"
          value={repository.scans.total}
          detail={latestScan ? `${latestScan.analyzerVersion} analyzer` : "Awaiting first scan"}
        />
        <MetricCard
          label="Last activity"
          value={formatDate(repository.updatedAt)}
          detail={repository.defaultBranch ?? "Branch not reported"}
        />
      </div>

      <section className="content-card trend-card">
        <div className="section-heading">
          <div>
            <p className="section-kicker">Risk trend</p>
            <h2>Findings over recent scans</h2>
          </div>
          <span className="muted-label">{repository.trend.length} data points</span>
        </div>
        {repository.trend.length === 0 ? (
          <StatePanel
            kind="empty"
            title="No trend data yet"
            description="Trend charts will appear after this repository has completed more than one scan."
          />
        ) : (
          <RiskTrend points={repository.trend} />
        )}
      </section>

      <div className="two-column-grid">
        <section className="content-card">
          <div className="section-heading">
            <div>
              <p className="section-kicker">Scan history</p>
              <h2>Recent scans</h2>
            </div>
            <span className="muted-label">{repository.scans.total} total</span>
          </div>
          {repository.scans.items.length === 0 ? (
            <StatePanel
              kind="empty"
              title="No scans yet"
              description="Ingest the first CI scan to start tracking repository health."
            />
          ) : (
            <ScanTable scans={repository.scans.items} repositoryId={repository.id} />
          )}
        </section>

        <section className="content-card">
          <div className="section-heading">
            <div>
              <p className="section-kicker">Findings</p>
              <h2>Recent findings</h2>
            </div>
            <span className="muted-label">{repository.recentFindings.length} shown</span>
          </div>
          {repository.recentFindings.length === 0 ? (
            <StatePanel
              kind="empty"
              title="No findings"
              description="This repository has no findings in the latest available scan."
            />
          ) : (
            <FindingList findings={repository.recentFindings} compact />
          )}
        </section>
      </div>

      <section className="two-column-grid context-grid">
        <div className="content-card context-card">
          <div className="section-heading">
            <div>
              <p className="section-kicker">Baseline comparison</p>
              <h2>Change since baseline</h2>
            </div>
          </div>
          {repository.baseline?.available ? (
            <div className="comparison-grid">
              <MetricCard label="New" value={repository.baseline.newFindings} tone="danger" />
              <MetricCard label="Resolved" value={repository.baseline.resolvedFindings} tone="positive" />
              <MetricCard label="Unchanged" value={repository.baseline.unchangedFindings} />
            </div>
          ) : (
            <StatePanel
              kind="empty"
              title="No baseline configured"
              description="Baseline comparisons will appear when the API records a reference scan."
            />
          )}
        </div>

        <div className="content-card context-card">
          <div className="section-heading">
            <div>
              <p className="section-kicker">Pull requests</p>
              <h2>Review context</h2>
            </div>
          </div>
          {repository.pullRequests.length === 0 ? (
            <StatePanel
              kind="empty"
              title="No pull-request context"
              description="Pull-request scan links will appear here when GitHub App results are available."
            />
          ) : (
            <ul className="context-list">
              {repository.pullRequests.map((pullRequest) => (
                <li key={`${pullRequest.number}-${pullRequest.headSha}`}>
                  <div>
                    <strong>#{pullRequest.number}</strong>
                    <span>{pullRequest.title ?? "Untitled pull request"}</span>
                  </div>
                  <span className={`pr-status pr-${pullRequest.status}`}>{pullRequest.status}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>
    </AppShell>
  );
}
