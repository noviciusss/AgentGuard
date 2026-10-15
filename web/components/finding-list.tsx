import type { Finding } from "@/lib/api";
import { StatusBadge } from "@/components/status-badge";

interface FindingListProps {
  findings: Finding[];
  compact?: boolean;
}

export function FindingList({ findings, compact = false }: FindingListProps) {
  return (
    <div className={`finding-list${compact ? " finding-list-compact" : ""}`}>
      {findings.map((finding) => (
        <article className="finding-card" key={finding.id || finding.fingerprint}>
          <div className="finding-card-topline">
            <div className="finding-tags">
              <span className="rule-id">{finding.ruleId}</span>
              <StatusBadge value={finding.severity} />
              <StatusBadge value={finding.confidence} />
            </div>
            <code>
              {finding.file}:{finding.line}:{finding.col}
            </code>
          </div>
          <h3>{finding.message}</h3>
          {!compact ? (
            <>
              <p className="finding-why">
                <strong>Why it matters.</strong> {finding.why}
              </p>
              <p className="finding-fix">
                <strong>Remediation.</strong> {finding.suggestion}
              </p>
            </>
          ) : null}
        </article>
      ))}
    </div>
  );
}
