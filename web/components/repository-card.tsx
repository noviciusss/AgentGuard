import Link from "next/link";
import type { RepositorySummary } from "@/lib/api";
import { StatusBadge } from "@/components/status-badge";

interface RepositoryCardProps {
  repository: RepositorySummary;
}

export function RepositoryCard({ repository }: RepositoryCardProps) {
  const latestScan = repository.latestScan;
  return (
    <Link className="repository-card" href={`/repositories/${repository.id}`}>
      <div className="repository-card-heading">
        <div>
          <p className="provider-label">{repository.provider}</p>
          <h2>{repository.fullName}</h2>
        </div>
        <span className="arrow" aria-hidden="true">
          →
        </span>
      </div>
      <div className="repository-card-meta">
        <span>{repository.defaultBranch ?? "No default branch"}</span>
        <span>{repository.findingCount} open findings</span>
      </div>
      <div className="repository-card-footer">
        {latestScan ? (
          <>
            <StatusBadge value={latestScan.status} />
            <span>
              Latest scan · {latestScan.findingCount} {latestScan.findingCount === 1 ? "finding" : "findings"}
            </span>
          </>
        ) : (
          <span>No scans recorded yet</span>
        )}
      </div>
    </Link>
  );
}
