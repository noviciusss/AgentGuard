"""AG002: detect unsafe mutable state shared by parallel agent branches."""

from __future__ import annotations

from collections.abc import Iterable

from agentguard.findings import Confidence, Finding, Severity
from agentguard.ir.models import AgentGraph, AgentNode, ModuleFacts
from agentguard.rules.base import Rule, RuleContext


class SharedMutableFanoutRule(Rule):
    """Report unreduced graph writes and concurrent mutable mutations."""

    rule_id = "AG002"
    name = "shared-mutable-fanout"
    description = (
        "Parallel branches that write shared mutable state without safe merging."
    )
    default_severity = Severity.ERROR

    def check(self, context: RuleContext) -> Iterable[Finding]:
        """Inspect graph fan-outs and generic concurrency facts."""
        for module in context.system.modules:
            for graph in module.graphs:
                if graph.framework == "langgraph":
                    yield from self._langgraph_findings(graph)
                else:
                    yield from self._generic_findings(module, graph)

    def _langgraph_findings(self, graph: AgentGraph) -> Iterable[Finding]:
        for fanout in graph.fan_outs:
            nodes = [graph.nodes.get(branch) for branch in fanout.branches]
            resolved = [node for node in nodes if node is not None]
            writes: dict[str, list[AgentNode]] = {}
            for node in resolved:
                for key in node.writes_state:
                    writes.setdefault(key, []).append(node)
            for key, writers in writes.items():
                state_key = graph.state_keys.get(key)
                if state_key is None or state_key.has_reducer:
                    continue
                if fanout.mechanism == "send_api" and len(writers) < 1:
                    continue
                if fanout.mechanism != "send_api" and len(writers) < 2:
                    continue
                confidence = (
                    Confidence.HIGH
                    if len(resolved) == len(fanout.branches)
                    else Confidence.MEDIUM
                )
                yield Finding(
                    rule_id=self.rule_id,
                    severity=Severity.ERROR,
                    confidence=confidence,
                    message=(
                        f"Parallel branches write state key {key!r} without a reducer."
                    ),
                    why=(
                        "Concurrent updates can overwrite each other or raise "
                        "InvalidUpdateError."
                    ),
                    suggestion=(
                        "Annotate the key with a reducer that safely merges branch "
                        "updates."
                    ),
                    loc=fanout.loc,
                    related=tuple(node.loc for node in writers),
                )

    def _generic_findings(
        self, module: ModuleFacts, graph: AgentGraph
    ) -> Iterable[Finding]:
        mutable_names = set(module.module_mutables)
        for fanout in graph.fan_outs:
            nodes = [graph.nodes.get(branch) for branch in fanout.branches]
            resolved = [node for node in nodes if node is not None]
            seen_nodes: set[str] = set()
            for node in resolved:
                if node.name in seen_nodes:
                    continue
                seen_nodes.add(node.name)
                for name in sorted(node.writes_state & mutable_names):
                    if name in node.protected_writes:
                        continue
                    yield Finding(
                        rule_id=self.rule_id,
                        severity=Severity.WARNING,
                        confidence=(
                            Confidence.HIGH
                            if len(resolved) == len(fanout.branches)
                            else Confidence.MEDIUM
                        ),
                        message=f"Parallel task mutates shared module state {name!r}.",
                        why=(
                            "Concurrent mutation can race and lose updates between "
                            "agent branches."
                        ),
                        suggestion=(
                            "Use per-task state or protect the mutation with an "
                            "appropriate lock."
                        ),
                        loc=fanout.loc,
                    )
                for argument in sorted(node.mutable_default_args):
                    yield Finding(
                        rule_id=self.rule_id,
                        severity=Severity.WARNING,
                        confidence=Confidence.HIGH,
                        message=(
                            f"Parallel task has mutable default argument {argument!r}."
                        ),
                        why=(
                            "The default object is shared across invocations and "
                            "branches."
                        ),
                        suggestion=(
                            "Use None as the default and create a fresh mutable "
                            "value per call."
                        ),
                        loc=fanout.loc,
                    )
