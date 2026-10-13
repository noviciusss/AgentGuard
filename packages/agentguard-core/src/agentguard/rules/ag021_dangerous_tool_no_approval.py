"""AG021: detect dangerous tools without an approval gate."""

from collections.abc import Iterable

from agentguard.findings import Finding, Severity
from agentguard.rules.base import Rule, RuleContext
from agentguard.rules.phase3_common import dangerous_tool_name, finding


class DangerousToolNoApprovalRule(Rule):
    """Report dangerous tool calls that lack a known human approval gate."""

    rule_id = "AG021"
    name = "dangerous-tool-no-approval"
    description = "Shell, deletion, payment, or write tools without approval."
    default_severity = Severity.ERROR

    def check(self, context: RuleContext) -> Iterable[Finding]:
        for module in context.system.modules:
            for call in module.call_sites:
                if (
                    call.kind == "tool"
                    and dangerous_tool_name(call.qualified_name)
                    and not call.approval_gate
                ):
                    yield finding(
                        self.rule_id,
                        call.loc,
                        "Dangerous tool is used without an approval gate.",
                        "An agent may perform an irreversible action without human "
                        "review.",
                        "Require explicit approval before invoking the dangerous tool.",
                        severity=Severity.ERROR,
                    )
