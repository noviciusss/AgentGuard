from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict


class State(TypedDict):
    items: list[str]


def left(state: State):
    return {"items": ["left"]}


def right(state: State):
    return {"items": ["right"]}


builder = StateGraph(State)  # expect: AG002
builder.add_node("left", left)
builder.add_node("right", right)
builder.add_edge(START, "left")
builder.add_edge(START, "right")
builder.add_edge("left", END)
builder.add_edge("right", END)
