"""AG007: detect conditional graph edges without resolved destinations."""

from collections.abc import Iterable

from agentguard.findings import Confidence, Finding, Severity
from agentguard.rules.base import Rule, RuleContext
from agentguard.rules.phase3_common import finding


class ConditionalEdgeUnmappedKeyRule(Rule):
    """Report conditional routing whose destination is unresolved."""

    rule_id = "AG007"
    name = "conditional-edge-unmapped-key"
    description = "Conditional graph routes with an unmapped destination key."
    default_severity = Severity.WARNING

    def check(self, context: RuleContext) -> Iterable[Finding]:
        for module in context.system.modules:
            for graph in module.graphs:
                for edge in graph.edges:
                    if (
                        edge.conditional
                        and edge.target is None
                        and edge.source not in graph.terminals
                    ):
                        yield finding(
                            self.rule_id,
                            edge.loc,
                            "Conditional graph route has no mapped destination.",
                            "An unmapped route can stop the agent or fail at runtime.",
                            "Provide a complete path map for every routing key.",
                            confidence=Confidence.MEDIUM,
                        )
