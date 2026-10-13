"""Reporter interface for already-analyzed findings."""

from abc import ABC, abstractmethod
from collections.abc import Iterable
from typing import ClassVar

from agentguard.findings import Finding


class Reporter(ABC):
    """Render findings without inspecting or re-analyzing source."""

    format_name: ClassVar[str] = ""

    @abstractmethod
    def render(self, findings: Iterable[Finding]) -> str:
        """Return a deterministic report string."""
