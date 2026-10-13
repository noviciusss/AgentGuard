"""Focused behavior tests for the Phase 3 rule catalog."""

from pathlib import Path

from agentguard.adapters.crewai import CrewAIAdapter
from agentguard.engine.parser import parse_source
from agentguard.findings import Finding
from agentguard.ir.builder import IRBuilder
from agentguard.plugins.manager import PluginManager
from agentguard.rules.base import RuleContext


def findings_for(source: str) -> list[Finding]:
    module = parse_source(source, Path("agent.py"))
    manager = PluginManager.default()
    system = IRBuilder([adapter() for adapter in manager.adapters()]).build_system(
        [module]
    )
    context = RuleContext(system, sources={Path("agent.py"): source})
    findings: list[Finding] = []
    for rule_class in manager.rules():
        findings.extend(rule_class().run(context))
    return findings


def rule_ids(source: str) -> set[str]:
    return {finding.rule_id for finding in findings_for(source)}


def test_phase_three_rules_cover_graph_cost_and_state_shapes() -> None:
    source = """
from langgraph.graph import START, StateGraph
from openai import OpenAI
from typing_extensions import TypedDict

class State(TypedDict):
    value: str

def first(state: State):
    return {"value": "first"}

def second(state: State):
    return {"value": "second"}

def orphan(state: State):
    return {"value": "orphan"}

client = OpenAI(timeout=30)
builder = StateGraph(State)
builder.add_node("first", first)
builder.add_node("second", second)
builder.add_node("orphan", orphan)
builder.add_edge(START, "first")
builder.add_edge("first", "second")
builder.add_edge("second", "first")

def ask(state):
    while True:
        state["messages"].append("x")
        client.responses.create(model="latest", input="x")
"""

    assert {"AG004", "AG005", "AG006", "AG010", "AG011"} <= rule_ids(source)


def test_phase_three_security_rules_cover_taint_tools_and_secrets() -> None:
    source = """
from openai import OpenAI
import subprocess

api_key = "sk-1234567890123456"
client = OpenAI(timeout=30)

def tool():
    try:
        return delete_tool()
    except Exception:
        pass

def run():
    user = input("prompt")
    output = client.responses.create(model="gpt-4", input=user)
    SystemMessage(system_prompt=user)
    eval(output)
    subprocess.run(output)
    while True:
        delete_tool()
"""

    assert {
        "AG008",
        "AG009",
        "AG020",
        "AG021",
        "AG022",
        "AG023",
    } <= rule_ids(source)


def test_phase_three_framework_adapters_remain_ir_only() -> None:
    source = "from crewai import Agent\nagent = Agent(max_iter=3)\n"
    facts = CrewAIAdapter().build(parse_source(source, Path("agent.py")))

    assert facts.graphs[0].framework == "crewai"
    assert facts.graphs[0].iteration_limit == 3
