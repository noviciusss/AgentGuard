"""Adapter interface for framework-specific IR construction."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

from agentguard.engine.parser import ParsedModule
from agentguard.ir.models import ModuleFacts


class FrameworkAdapter(ABC):
    """Translate one parsed Python module into normalized Agent IR facts."""

    name: str
    priority: ClassVar[int] = 1000

    @abstractmethod
    def can_handle(self, module: ParsedModule) -> bool:
        """Return whether this adapter recognizes the module."""

    @abstractmethod
    def build(self, module: ParsedModule) -> ModuleFacts:
        """Build facts without emitting findings."""
