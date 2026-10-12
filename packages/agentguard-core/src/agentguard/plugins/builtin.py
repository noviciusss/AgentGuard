"""Built-in contributions exposed through the public plugin boundary."""

from __future__ import annotations

from agentguard.adapters.autogen import AutoGenAdapter
from agentguard.adapters.crewai import CrewAIAdapter
from agentguard.adapters.generic import GenericAdapter
from agentguard.plugins.spec import hookimpl
from agentguard.reporters.json_reporter import JsonReporter
from agentguard.reporters.text import TextReporter
from agentguard.rules.ag001_unbounded_retries import UnboundedRetriesRule
from agentguard.rules.ag002_shared_mutable_fanout import SharedMutableFanoutRule
from agentguard.rules.ag003_missing_timeout import MissingTimeoutRule
from agentguard.rules.ag004_unbounded_agent_loop import UnboundedAgentLoopRule
from agentguard.rules.ag005_no_cost_budget import NoCostBudgetRule
from agentguard.rules.ag006_unreachable_graph_node import UnreachableGraphNodeRule
from agentguard.rules.ag007_conditional_edge_unmapped_key import (
    ConditionalEdgeUnmappedKeyRule,
)
from agentguard.rules.ag008_exception_swallowed_in_tool import (
    ExceptionSwallowedInToolRule,
)
from agentguard.rules.ag009_non_idempotent_tool_with_retry import (
    NonIdempotentToolWithRetryRule,
)
from agentguard.rules.ag010_unpinned_model_alias import UnpinnedModelAliasRule
from agentguard.rules.ag011_unbounded_state_growth import UnboundedStateGrowthRule
from agentguard.rules.ag020_prompt_injection_sink import PromptInjectionSinkRule
from agentguard.rules.ag021_dangerous_tool_no_approval import (
    DangerousToolNoApprovalRule,
)
from agentguard.rules.ag022_llm_output_to_sink import LlmOutputToSinkRule
from agentguard.rules.ag023_hardcoded_secret import HardcodedSecretRule
from agentguard.rules.base import Rule


class BuiltinPlugin:
    """Register the rules, adapters, and reporters shipped by AgentGuard."""

    name = "agentguard-builtins"

    @hookimpl
    def register_rules(self) -> list[type[Rule]]:
        return [
            UnboundedRetriesRule,
            SharedMutableFanoutRule,
            MissingTimeoutRule,
            UnboundedAgentLoopRule,
            NoCostBudgetRule,
            UnreachableGraphNodeRule,
            ConditionalEdgeUnmappedKeyRule,
            ExceptionSwallowedInToolRule,
            NonIdempotentToolWithRetryRule,
            UnpinnedModelAliasRule,
            UnboundedStateGrowthRule,
            PromptInjectionSinkRule,
            DangerousToolNoApprovalRule,
            LlmOutputToSinkRule,
            HardcodedSecretRule,
        ]

    @hookimpl
    def register_adapters(self) -> list[type]:
        return [CrewAIAdapter, AutoGenAdapter, GenericAdapter]

    @hookimpl
    def register_reporters(self) -> list[type]:
        return [TextReporter, JsonReporter]
