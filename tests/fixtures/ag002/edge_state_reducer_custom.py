from typing import Annotated

from langgraph.graph import START, StateGraph
from typing_extensions import TypedDict


def merge(left, right):
    return left + right


class State(TypedDict):
    values: Annotated[list[str], merge]


def a(state: State):
    return {"values": ["a"]}


def b(state: State):
    return {"values": ["b"]}


builder = StateGraph(State)
builder.add_node("a", a)
builder.add_node("b", b)
builder.add_edge(START, "a")
builder.add_edge(START, "b")
