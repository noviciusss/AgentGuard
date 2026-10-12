"""Tests for the conservative CrewAI and AutoGen adapters."""

from pathlib import Path

from agentguard.adapters.autogen import AutoGenAdapter
from agentguard.adapters.crewai import CrewAIAdapter
from agentguard.engine.parser import parse_source


def test_crewai_adapter_extracts_max_iter_without_importing_crewai() -> None:
    source = """
from crewai import Agent, Crew

agent = Agent(role="researcher", max_iter=4)
crew = Crew(agents=[agent], tasks=[], process="sequential")
"""
    module = parse_source(source, Path("crew.py"))

    assert CrewAIAdapter().can_handle(module)
    facts = CrewAIAdapter().build(module)
    assert facts.graphs[0].framework == "crewai"
    assert facts.graphs[0].iteration_limit == 4


def test_autogen_adapter_extracts_max_round_without_importing_autogen() -> None:
    source = """
from autogen import AssistantAgent, GroupChat

assistant = AssistantAgent("assistant")
chat = GroupChat(agents=[assistant], max_round=6)
"""
    module = parse_source(source, Path("chat.py"))

    assert AutoGenAdapter().can_handle(module)
    facts = AutoGenAdapter().build(module)
    assert facts.graphs[0].framework == "autogen"
    assert facts.graphs[0].iteration_limit == 6
