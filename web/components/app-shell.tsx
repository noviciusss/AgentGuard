import Link from "next/link";
import type { ReactNode } from "react";

interface AppShellProps {
  children: ReactNode;
  eyebrow?: string;
  title?: string;
  description?: string;
}

export function AppShell({
  children,
  eyebrow,
  title,
  description
}: AppShellProps) {
  return (
    <div className="app-shell">
      <header className="topbar">
        <Link className="brand" href="/" aria-label="AgentGuard dashboard home">
          <span className="brand-mark" aria-hidden="true">
            A
          </span>
          <span>AgentGuard</span>
        </Link>
        <nav className="topnav" aria-label="Primary navigation">
          <Link href="/">Repositories</Link>
          <span className="topnav-status">
            <span className="status-dot" aria-hidden="true" />
            Platform dashboard
          </span>
        </nav>
      </header>
      <main className="page-shell">
        {title ? (
          <div className="page-heading">
            {eyebrow ? <p className="eyebrow">{eyebrow}</p> : null}
            <h1>{title}</h1>
            {description ? <p className="page-description">{description}</p> : null}
          </div>
        ) : null}
        {children}
      </main>
    </div>
  );
}
