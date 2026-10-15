interface MetricCardProps {
  label: string;
  value: string | number;
  detail?: string;
  tone?: "neutral" | "danger" | "warning" | "positive";
}

export function MetricCard({ label, value, detail, tone = "neutral" }: MetricCardProps) {
  return (
    <div className={`metric-card metric-${tone}`}>
      <p>{label}</p>
      <strong>{value}</strong>
      {detail ? <span>{detail}</span> : null}
    </div>
  );
}
