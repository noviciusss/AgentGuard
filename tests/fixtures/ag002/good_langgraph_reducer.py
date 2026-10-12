from operator import add
from typing import Annotated

from langgraph.graph import START, StateGraph
from typing_extensions import TypedDict


class State(TypedDict):
    items: Annotated[list[str], add]


def left(state: State):
    return {"items": ["left"]}


def right(state: State):
    return {"items": ["right"]}


builder = StateGraph(State)
builder.add_node("left", left)
builder.add_node("right", right)
builder.add_edge(START, "left")
builder.add_edge(START, "right")
