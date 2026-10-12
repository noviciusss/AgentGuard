"""Conservative AST adapter for common AutoGen construction patterns."""

from __future__ import annotations

import ast
from dataclasses import replace

from agentguard.adapters.base import FrameworkAdapter
from agentguard.adapters.generic import GenericAdapter
from agentguard.engine.parser import ParsedModule
from agentguard.ir.models import ModuleFacts


class AutoGenAdapter(FrameworkAdapter):
    """Normalize AutoGen agents and group-chat round limits."""

    name = "autogen"
    priority = 300

    def can_handle(self, module: ParsedModule) -> bool:
        """Recognize AutoGen imports and common agent constructors."""
        return any(
            isinstance(node, ast.ImportFrom)
            and (node.module or "").startswith(("autogen", "autogen_agentchat"))
            for node in ast.walk(module.tree)
        ) or any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in {"GroupChat", "AssistantAgent", "UserProxyAgent"}
            for node in ast.walk(module.tree)
        )

    def build(self, module: ParsedModule) -> ModuleFacts:
        """Build generic facts and annotate their graph as AutoGen."""
        facts = GenericAdapter().build(module)
        limit = _keyword_int(module.tree, {"max_round", "max_rounds"})
        graphs = [
            replace(
                graph,
                framework="autogen",
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
