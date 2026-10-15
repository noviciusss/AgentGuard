import { ApiError } from "@/lib/api";
import { StatePanel } from "@/components/state-panel";

interface ApiStateProps {
  error: ApiError;
  resource: string;
  retryHref?: string;
}

export function ApiState({ error, resource, retryHref = "/" }: ApiStateProps) {
  if (error.kind === "forbidden") {
    return (
      <StatePanel
        kind="forbidden"
        title="Access restricted"
        description={`You do not have permission to view this ${resource}. Sign in with an account that can access the repository, then try again.`}
        actionHref={retryHref}
        actionLabel="Try again"
      />
    );
  }

  if (error.kind === "unavailable") {
    return (
      <StatePanel
        kind="unavailable"
        title="Dashboard service unavailable"
        description="The AgentGuard API is unavailable right now. Check the service status or try again in a moment."
        actionHref={retryHref}
        actionLabel="Retry request"
      />
    );
  }

  return (
    <StatePanel
      kind="error"
      title={`Could not load ${resource}`}
      description={error.message}
      actionHref={retryHref}
      actionLabel="Retry request"
    />
  );
}
