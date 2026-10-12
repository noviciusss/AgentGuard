"""AG006: detect unreachable graph nodes."""

from collections.abc import Iterable

from agentguard.findings import Finding, Severity
from agentguard.rules.base import Rule, RuleContext
from agentguard.rules.phase3_common import finding


class UnreachableGraphNodeRule(Rule):
    """Report graph nodes that cannot be reached from the entry point."""

    rule_id = "AG006"
    name = "unreachable-graph-node"
    description = "Agent graph nodes that have no path from the entry point."
    default_severity = Severity.WARNING

    def check(self, context: RuleContext) -> Iterable[Finding]:
        for module in context.system.modules:
            for graph in module.graphs:
                for name in sorted(graph.unreachable_nodes):
                    node = graph.nodes[name]
                    yield finding(
                        self.rule_id,
                        node.loc,
                        f"Graph node {name!r} is unreachable from the entry point.",
                        "Dead nodes are never executed and often indicate a wiring "
                        "mistake.",
                        "Connect the node to the entry path or remove it.",
                    )
