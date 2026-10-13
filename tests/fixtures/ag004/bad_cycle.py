from langgraph.graph import START, StateGraph

builder = StateGraph(dict)  # expect: AG004


def first(state):
    return state


def second(state):
    return state


builder.add_node("first", first)
builder.add_node("second", second)
builder.add_edge(START, "first")
builder.add_edge("first", "second")
builder.add_edge("second", "first")
