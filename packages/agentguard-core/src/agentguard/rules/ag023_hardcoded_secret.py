"""AG023: detect likely credentials embedded in source."""

from collections.abc import Iterable

from agentguard.findings import Finding, Severity
from agentguard.rules.base import Rule, RuleContext
from agentguard.rules.phase3_common import finding


class HardcodedSecretRule(Rule):
    """Report likely literal credentials and API keys."""

    rule_id = "AG023"
    name = "hardcoded-secret"
    description = "Likely API keys, passwords, or credentials hardcoded in source."
    default_severity = Severity.ERROR

    def check(self, context: RuleContext) -> Iterable[Finding]:
        for module in context.system.modules:
            for secret in module.secrets:
                yield finding(
                    self.rule_id,
                    secret.loc,
                    f"Likely hardcoded {secret.kind} {secret.name!r}.",
                    "Committed credentials can be copied and abused by anyone with "
                    "source access.",
                    "Load the value from a secret manager or environment "
                    "configuration.",
                    severity=Severity.ERROR,
                )
