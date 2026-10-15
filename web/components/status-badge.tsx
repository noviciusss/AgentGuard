import type { FindingConfidence, FindingSeverity, ScanStatus } from "@/lib/api";

type BadgeValue = ScanStatus | FindingSeverity | FindingConfidence;

interface StatusBadgeProps {
  value: BadgeValue;
}

export function StatusBadge({ value }: StatusBadgeProps) {
  return <span className={`badge badge-${value}`}>{value}</span>;
}
