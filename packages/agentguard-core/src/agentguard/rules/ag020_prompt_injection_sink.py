"""AG020: detect untrusted data flowing into system prompts."""

from collections.abc import Iterable

from agentguard.findings import Finding, Severity
from agentguard.ir.models import DataSource, TaintSink
from agentguard.rules.base import Rule, RuleContext
from agentguard.rules.phase3_common import finding


class PromptInjectionSinkRule(Rule):
    """Report user or tool data reaching privileged prompt inputs."""

    rule_id = "AG020"
    name = "prompt-injection-sink"
    description = "User or tool output flows into a system prompt."
    default_severity = Severity.ERROR

    def check(self, context: RuleContext) -> Iterable[Finding]:
        for module in context.system.modules:
            for flow in module.taint_flows:
                if flow.sink == TaintSink.SYSTEM_PROMPT and flow.source in {
                    DataSource.USER_INPUT,
                    DataSource.TOOL_OUTPUT,
                }:
                    yield finding(
                        self.rule_id,
                        flow.loc,
                        "Untrusted data flows into a system prompt.",
                        "Injected instructions can override the agent's privileged "
                        "behavior.",
                        "Keep untrusted content in a separate user-data message and "
                        "validate it.",
                        severity=Severity.ERROR,
                    )
