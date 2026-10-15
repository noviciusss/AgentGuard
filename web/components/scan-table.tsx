import Link from "next/link";
import type { ScanSummary } from "@/lib/api";
import { StatusBadge } from "@/components/status-badge";

interface ScanTableProps {
  scans: ScanSummary[];
  repositoryId: string;
}

const formatDate = (value: string): string =>
  new Intl.DateTimeFormat("en", {
    dateStyle: "medium",
    timeStyle: "short"
  }).format(new Date(value));

export function ScanTable({ scans, repositoryId }: ScanTableProps) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Scan</th>
            <th>Status</th>
            <th>Findings</th>
            <th>Analyzer</th>
            <th>Created</th>
          </tr>
        </thead>
        <tbody>
          {scans.map((scan) => (
            <tr key={scan.id}>
              <td>
                <Link className="table-link" href={`/repositories/${repositoryId}/scans/${scan.id}`}>
                  <strong>{scan.scanKey}</strong>
                </Link>
              </td>
              <td>
                <StatusBadge value={scan.status} />
              </td>
              <td>{scan.findingCount}</td>
              <td>{scan.analyzerVersion}</td>
              <td>{formatDate(scan.createdAt)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
