"""AG003: detect network and model calls without a configured timeout."""

from __future__ import annotations

from collections.abc import Iterable

from agentguard.findings import Confidence, Finding, Severity
from agentguard.ir.models import AgentSystem, CallSite
from agentguard.rules.base import Rule, RuleContext


class MissingTimeoutRule(Rule):
    """Report known calls that can wait indefinitely or too long."""

    rule_id = "AG003"
    name = "missing-timeout"
    description = "Network and LLM calls without an explicit or configured timeout."
    default_severity = Severity.WARNING

    def check(self, context: RuleContext) -> Iterable[Finding]:
        """Inspect only normalized call sites from adapters."""
        for module in context.system.modules:
            for call in module.call_sites:
                if call.kind not in {"http", "llm", "tool"}:
                    continue
                if call.has_timeout is not False:
                    continue
                yield self._finding(call, context.system)

    def _finding(self, call: CallSite, system: AgentSystem) -> Finding:
        is_langchain = (
            "ChatOpenAI" in call.qualified_name
            or "ChatAnthropic" in call.qualified_name
        )
        is_aiohttp = call.qualified_name.startswith("aiohttp.")
        confidence = Confidence.MEDIUM if is_langchain else Confidence.HIGH
        severity = Severity.INFO if is_aiohttp else Severity.WARNING
        if call.in_loop or (call.kind == "http" and _has_llm_call(system)):
            severity = Severity.ERROR
        return Finding(
            rule_id=self.rule_id,
            severity=severity,
            confidence=confidence if not is_aiohttp else Confidence.LOW,
            message=f"{call.qualified_name} has no timeout",
            why="A hung provider connection can block the agent indefinitely.",
            suggestion="Pass timeout=<seconds> or configure a client-level timeout.",
            loc=call.loc,
        )


def _has_llm_call(system: AgentSystem) -> bool:
    return any(
        call.kind == "llm" for module in system.modules for call in module.call_sites
    )
