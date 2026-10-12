"""Reporter interface for already-analyzed findings."""

from abc import ABC, abstractmethod
from collections.abc import Iterable

from agentguard.findings import Finding


class Reporter(ABC):
    """Render findings without inspecting or re-analyzing source."""

    @abstractmethod
    def render(self, findings: Iterable[Finding]) -> str:
        """Return a deterministic report string."""
