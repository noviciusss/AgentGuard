from langgraph.graph import StateGraph
from langgraph.types import Send
from typing_extensions import TypedDict


class State(TypedDict):
    results: list[str]


def worker(state: State):
    return {"results": ["done"]}


def route(state: State):
    return [Send("worker", {}) for _ in state["results"]]  # expect: AG002


builder = StateGraph(State)
builder.add_node(worker)
builder.add_conditional_edges("route", route)
