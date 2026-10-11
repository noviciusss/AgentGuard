"""Tests for generic adapter call and loop extraction."""

from pathlib import Path

from agentguard.adapters.generic import GenericAdapter
from agentguard.engine.parser import parse_source
from agentguard.ir.calls import TimeoutMode, lookup_known_call


def test_known_call_table_classifies_timeout_families() -> None:
    requests_call = lookup_known_call("requests.get")
    httpx_call = lookup_known_call("httpx.get")
    openai_call = lookup_known_call("openai.OpenAI")
    assert requests_call is not None
    assert httpx_call is not None
    assert openai_call is not None
    assert requests_call.timeout_mode == TimeoutMode.REQUIRED
    assert httpx_call.timeout_mode == TimeoutMode.DEFAULT
    assert openai_call.client_family == "openai"


def test_generic_adapter_resolves_aliases_clients_calls_and_loops() -> None:
    source = """
import requests as r
from openai import OpenAI
from tenacity import retry, stop_after_attempt

client = OpenAI(timeout=30)
cache = {}

@retry(stop=stop_after_attempt(3))
def answer(state):
    while True:
        cache.update(state)
        response = client.chat.completions.create(model='x')
        r.get('https://example.com')
        return response
"""
    facts = GenericAdapter().build(parse_source(source, Path("agent.py")))

    assert facts.imports["r"] == "requests"
    assert set(facts.module_mutables) == {"cache"}
    assert [call.qualified_name for call in facts.call_sites] == [
        "openai.OpenAI",
        "openai.chat.completions.create",
        "requests.get",
    ]
    assert facts.call_sites[1].kind == "llm"
    assert facts.call_sites[1].has_timeout is True
    assert facts.call_sites[2].has_timeout is False
    assert any(loop.kind == "while" and loop.has_bound is False for loop in facts.loops)
    assert any(
        loop.kind == "retry_decorator" and loop.has_bound is True
        for loop in facts.loops
    )


def test_generic_adapter_emits_parallel_fanout_and_mutable_default() -> None:
    source = """
from concurrent.futures import ThreadPoolExecutor

shared = {}

def worker(state, cache={}):
    shared['value'] = state

with ThreadPoolExecutor() as pool:
    pool.submit(worker, {})
"""
    facts = GenericAdapter().build(parse_source(source, Path("agent.py")))
    graph = facts.graphs[0]

    assert graph.fan_outs[0].mechanism == "thread_pool"
    assert graph.fan_outs[0].branches == ["worker"]
    assert graph.nodes["worker"].mutable_default_args == {"cache"}
    assert graph.nodes["worker"].writes_state == {"shared"}
