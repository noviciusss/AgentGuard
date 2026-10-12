"""AG022: detect generated output reaching executable sinks."""

from collections.abc import Iterable

from agentguard.findings import Finding, Severity
from agentguard.ir.models import DataSource, TaintSink
from agentguard.rules.base import Rule, RuleContext
from agentguard.rules.phase3_common import finding


class LlmOutputToSinkRule(Rule):
    """Report LLM output flowing to code, SQL, process, or file sinks."""

    rule_id = "AG022"
    name = "llm-output-to-sink"
    description = "LLM output reaches an executable or write sink."
    default_severity = Severity.ERROR

    def check(self, context: RuleContext) -> Iterable[Finding]:
        unsafe_sinks = {
            TaintSink.EVAL,
            TaintSink.EXEC,
            TaintSink.SUBPROCESS,
            TaintSink.SQL,
            TaintSink.FILE_PATH,
        }
        for module in context.system.modules:
            for flow in module.taint_flows:
                if flow.source == DataSource.LLM_OUTPUT and flow.sink in unsafe_sinks:
                    yield finding(
                        self.rule_id,
                        flow.loc,
                        "LLM output reaches a dangerous execution or write sink.",
                        "Generated text is untrusted and can execute code or alter "
                        "data.",
                        "Validate against an allowlist and use typed APIs instead of "
                        "raw sinks.",
                        severity=Severity.ERROR,
                    )
