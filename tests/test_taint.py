"""Tests for intra-function taint and secret facts."""

from pathlib import Path

from agentguard.engine.parser import parse_source
from agentguard.ir.models import DataSource, TaintSink
from agentguard.ir.taint import analyze_taint


def test_taint_tracks_user_and_llm_output_to_dangerous_sinks() -> None:
    source = """
from openai import OpenAI
import subprocess

client = OpenAI(timeout=30)

def run():
    prompt = input("prompt")
    output = client.responses.create(model="x", input=prompt)
    eval(output)
    subprocess.run(output)
"""
    module = parse_source(source, Path("agent.py"))
    facts = analyze_taint(module.tree, Path("agent.py"))

    assert any(
        flow.source == DataSource.LLM_OUTPUT and flow.sink == TaintSink.EVAL
        for flow in facts.flows
    )
    assert any(flow.sink == TaintSink.SUBPROCESS for flow in facts.flows)


def test_taint_finds_hardcoded_credentials_and_state_growth() -> None:
    source = """
api_key = "sk-1234567890123456"

def run(state):
    while True:
        state["messages"].append("new")
"""
    module = parse_source(source, Path("agent.py"))
    facts = analyze_taint(module.tree, Path("agent.py"))

    assert facts.secrets[0].name == "api_key"
    assert len(facts.state_growths) == 1
