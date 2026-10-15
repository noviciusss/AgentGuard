"""Argument-sensitive same-file inter-procedural taint tests."""

from pathlib import Path

from agentguard.adapters.generic import GenericAdapter
from agentguard.engine.parser import parse_source
from agentguard.ir.models import AgentSystem, DataSource
from agentguard.ir.taint import TaintFacts, analyze_taint
from agentguard.rules.ag022_llm_output_to_sink import LlmOutputToSinkRule
from agentguard.rules.base import RuleContext


def _analyze(source: str) -> TaintFacts:
    parsed = parse_source(source, Path("agent.py"))
    return analyze_taint(parsed.tree, parsed.path)


def test_argument_taint_reaches_helper_sink_and_rule_uses_ir_location() -> None:
    source = """
from openai import OpenAI

client = OpenAI(timeout=10)

def dispatch_to_eval(value):
    eval(value)

def run():
    output = client.responses.create(model="model", input="request")
    dispatch_to_eval(output)
"""
    parsed = parse_source(source, Path("agent.py"))
    facts = GenericAdapter().build(parsed)
    findings = LlmOutputToSinkRule().run(RuleContext(AgentSystem([facts])))

    assert [(finding.loc.line, finding.rule_id) for finding in findings] == [
        (7, "AG022")
    ]
    assert len(facts.taint_flows) == 1
    assert facts.taint_flows[0].source == DataSource.LLM_OUTPUT
    assert facts.taint_flows[0].loc.line == 7


def test_identity_overrides_formal_name_heuristic_for_clean_and_tainted_calls() -> None:
    facts = _analyze(
        """
def identity(prompt):
    return prompt

clean = identity("literal")
eval(clean)
tainted = identity(input("prompt"))
eval(tainted)
"""
    )

    assert [(flow.loc.line, flow.source) for flow in facts.flows] == [
        (8, DataSource.USER_INPUT)
    ]


def test_default_arguments_are_bound_instead_of_using_formal_name_heuristics() -> None:
    facts = _analyze(
        """
def identity(prompt="literal"):
    return prompt

def sink(value="literal"):
    eval(value)

clean = identity()
eval(clean)
sink()
"""
    )

    assert facts.flows == []


def test_forwarding_and_definition_order_with_keyword_only_args() -> None:
    facts = _analyze(
        """
def outer(value):
    return middle(value=value)

def middle(*, value, fallback="clean"):
    return identity(value, fallback)

def identity(value, fallback="clean"):
    return value

result = outer(input("prompt"))
eval(result)
"""
    )

    assert len(facts.flows) == 1
    assert facts.flows[0].source == DataSource.USER_INPUT
    assert facts.flows[0].loc.line == 12
    assert facts.call_graph == {
        "identity": (),
        "middle": ("identity",),
        "outer": ("middle",),
    }


def test_recursive_passthrough_and_recursive_source_terminate() -> None:
    facts = _analyze(
        """
def recursive(value):
    return recursive(value)

def sourced():
    return sourced() if False else input("prompt")

clean = recursive("literal")
eval(clean)
tainted = recursive(input("prompt"))
eval(tainted)
eval(sourced())
"""
    )

    assert [(flow.loc.line, flow.source) for flow in facts.flows] == [
        (11, DataSource.USER_INPUT),
        (12, DataSource.USER_INPUT),
    ]


def test_clean_overwrite_and_function_local_state_do_not_leak() -> None:
    facts = _analyze(
        """
def clean():
    value = input("ignored")
    value = "constant"
    eval(value)

def isolated():
    value = "constant"
    eval(value)

def tainted():
    value = input("prompt")
    eval(value)
"""
    )

    assert [(flow.loc.line, flow.function) for flow in facts.flows] == [(13, "tainted")]


def test_aliases_resolve_but_imported_and_dynamic_calls_are_unknown() -> None:
    facts = _analyze(
        """
from another_module import identity as imported_identity

def identity(value):
    return value

alias = identity
clean = alias("literal")
eval(clean)

cross_module = imported_identity(input("prompt"))
eval(cross_module)

dynamic = get_callable()(input("prompt"))
eval(dynamic)
"""
    )

    assert facts.flows == []


def test_class_and_nested_same_names_are_not_resolved_as_module_helpers() -> None:
    facts = _analyze(
        """
def helper(value):
    return value

class Container:
    def helper(value):
        return input("not a module helper")

def outer():
    def helper(value):
        return input("not a module helper")
    return helper("literal")

value = helper("literal")
eval(value)
"""
    )

    assert facts.flows == []
