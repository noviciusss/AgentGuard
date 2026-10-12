"""Conservative AST adapter for common CrewAI construction patterns."""

from __future__ import annotations

import ast
from dataclasses import replace

from agentguard.adapters.base import FrameworkAdapter
from agentguard.adapters.generic import GenericAdapter
from agentguard.engine.parser import ParsedModule
from agentguard.ir.models import ModuleFacts


class CrewAIAdapter(FrameworkAdapter):
    """Normalize CrewAI agents, tasks, crews, and iteration settings."""

    name = "crewai"
    priority = 200

    def can_handle(self, module: ParsedModule) -> bool:
        """Recognize CrewAI imports or constructor calls without importing it."""
        return any(
            isinstance(node, ast.ImportFrom)
            and (node.module or "").startswith("crewai")
            for node in ast.walk(module.tree)
        ) or any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in {"Agent", "Task", "Crew"}
            for node in ast.walk(module.tree)
        )

    def build(self, module: ParsedModule) -> ModuleFacts:
        """Build generic facts and annotate their graph as CrewAI."""
        facts = GenericAdapter().build(module)
        limit = _keyword_int(module.tree, {"max_iter", "max_iterations"})
        graphs = [
            replace(
                graph,
                framework="crewai",
                iteration_limit=limit,
                recursion_limit=limit,
            )
            for graph in facts.graphs
        ]
        return replace(facts, graphs=graphs)


def _keyword_int(tree: ast.Module, names: set[str]) -> int | None:
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        for keyword in node.keywords:
            if (
                keyword.arg in names
                and isinstance(keyword.value, ast.Constant)
                and isinstance(keyword.value.value, int)
            ):
                return keyword.value.value
    return None
