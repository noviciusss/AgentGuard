"use client";

import { useEffect } from "react";
import { AppShell } from "@/components/app-shell";
import { StatePanel } from "@/components/state-panel";

interface ErrorPageProps {
  error: Error & { digest?: string };
  reset: () => void;
}

export default function ErrorPage({ error, reset }: ErrorPageProps) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <AppShell>
      <StatePanel
        kind="error"
        title="Something went wrong"
        description="The dashboard could not render this view. Retry the request or return to the repository list."
        actionHref="/"
        actionLabel="Back to repositories"
      />
      <div className="error-actions">
        <button className="button button-primary" type="button" onClick={reset}>
          Try again
        </button>
      </div>
    </AppShell>
  );
}
