import Link from "next/link";

export type StatePanelKind =
  | "loading"
  | "empty"
  | "error"
  | "forbidden"
  | "unavailable";

interface StatePanelProps {
  kind: StatePanelKind;
  title: string;
  description: string;
  actionHref?: string;
  actionLabel?: string;
}

export function StatePanel({
  kind,
  title,
  description,
  actionHref,
  actionLabel
}: StatePanelProps) {
  return (
    <section className={`state-panel state-${kind}`} role={kind === "error" ? "alert" : "status"}>
      <span className="state-icon" aria-hidden="true">
        {kind === "loading" ? "…" : kind === "empty" ? "○" : kind === "forbidden" ? "×" : "!"}
      </span>
      <div>
        <h2>{title}</h2>
        <p>{description}</p>
        {actionHref && actionLabel ? (
          <Link className="button button-secondary" href={actionHref}>
            {actionLabel}
          </Link>
        ) : null}
      </div>
    </section>
  );
}
