import Link from "next/link";
import { ApiState } from "@/components/api-state";
import { AppShell } from "@/components/app-shell";
import { FindingList } from "@/components/finding-list";
import { MetricCard } from "@/components/metric-card";
import { StatusBadge } from "@/components/status-badge";
import { StatePanel } from "@/components/state-panel";
import { getScan, loadApi } from "@/lib/api";

interface ScanPageProps {
  params: { repositoryId: string; scanId: string };
}

export const dynamic = "force-dynamic";

const formatDate = (value: string): string =>
  new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));

export function generateMetadata() {
  return { title: "Scan" };
}

export default async function ScanPage({ params }: ScanPageProps) {
  const result = await loadApi(() => getScan(params.scanId));

  if (result.status === "error") {
    return (
      <AppShell>
        <ApiState error={result.error} resource="this scan" retryHref={`/repositories/${params.repositoryId}`} />
      </AppShell>
    );
  }

  const scan = result.data;
  return (
    <AppShell
      eyebrow="Scan detail"
      title={scan.scanKey}
      description={`${scan.analyzerVersion} analyzer · created ${formatDate(scan.createdAt)}`}
    >
      <div className="breadcrumb-row">
        <Link className="back-link" href={`/repositories/${params.repositoryId}`}>
          ← Repository overview
        </Link>
        <StatusBadge value={scan.status} />
      </div>

      <div className="metric-grid scan-summary-grid">
        <MetricCard label="Findings" value={scan.findingCount} tone={scan.findingCount ? "warning" : "positive"} />
        <MetricCard label="Branch" value={scan.branchName ?? "—"} />
        <MetricCard label="Commit" value={scan.commitSha ? scan.commitSha.slice(0, 12) : "—"} />
        <MetricCard label="Pull request" value={scan.pullRequest ? `#${scan.pullRequest.number}` : "None"} />
      </div>

      {scan.commitMessage ? (
        <section className="commit-note">
          <span className="section-kicker">Commit message</span>
          <p>{scan.commitMessage}</p>
        </section>
      ) : null}

      <section className="content-card finding-detail-card">
        <div className="section-heading">
          <div>
            <p className="section-kicker">Finding details</p>
            <h2>{scan.findings.length ? "Findings from this scan" : "Clean scan"}</h2>
          </div>
          <span className="muted-label">{scan.findings.length} total</span>
        </div>
        {scan.findings.length === 0 ? (
          <StatePanel
            kind="empty"
            title="No findings in this scan"
            description="The analyzer did not report a finding for this commit."
          />
        ) : (
          <FindingList findings={scan.findings} />
        )}
      </section>
    </AppShell>
  );
}
