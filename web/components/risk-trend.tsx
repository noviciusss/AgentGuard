import type { TrendPoint } from "@/lib/api";

interface RiskTrendProps {
  points: TrendPoint[];
}

const formatDate = (value: string): string =>
  new Intl.DateTimeFormat("en", { month: "short", day: "numeric" }).format(new Date(value));

export function RiskTrend({ points }: RiskTrendProps) {
  if (points.length === 0) {
    return null;
  }

  const maximum = Math.max(...points.map((point) => point.findingCount), 1);
  return (
    <div className="trend-chart" role="img" aria-label="Finding count trend over recent scans">
      <div className="trend-y-axis" aria-hidden="true">
        <span>{maximum}</span>
        <span>{Math.round(maximum / 2)}</span>
        <span>0</span>
      </div>
      <div className="trend-bars">
        {points.map((point) => (
          <div className="trend-column" key={point.date}>
            <div className="trend-bar-track">
              <div
                className="trend-bar"
                style={{ height: `${Math.max((point.findingCount / maximum) * 100, point.findingCount ? 5 : 0)}%` }}
                title={`${point.findingCount} findings on ${formatDate(point.date)}`}
              />
            </div>
            <span>{formatDate(point.date)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
