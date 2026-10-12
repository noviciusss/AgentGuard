"""AG010: detect model names that do not pin a provider revision."""

import re
from collections.abc import Iterable

from agentguard.findings import Finding, Severity
from agentguard.rules.base import Rule, RuleContext
from agentguard.rules.phase3_common import finding

_PINNED_MODEL = re.compile(r"(?:19|20)\d{2}(?:[-_]\d{2})?(?:[-_]\d{2})?")


class UnpinnedModelAliasRule(Rule):
    """Report literal LLM model aliases without a dated revision."""

    rule_id = "AG010"
    name = "unpinned-model-alias"
    description = "LLM model aliases that are not pinned to a revision."
    default_severity = Severity.WARNING

    def check(self, context: RuleContext) -> Iterable[Finding]:
        for module in context.system.modules:
            for call in module.call_sites:
                if call.kind != "llm" or call.model_name is None:
                    continue
                model = call.model_name.lower()
                if "latest" in model or not _PINNED_MODEL.search(model):
                    yield finding(
                        self.rule_id,
                        call.loc,
                        f"LLM model {call.model_name!r} is not revision-pinned.",
                        "Provider aliases can change behavior, availability, and cost.",
                        "Use a dated or otherwise provider-pinned model identifier.",
                    )
