from langgraph.graph import START, StateGraph


def one(state):
    return state


def two(state):
    return state


builder = StateGraph(dict)  # expect: AG004
builder.add_node("one", one)
builder.add_node("two", two)
builder.add_edge(START, "one")
builder.add_edge("one", "two")
builder.add_edge("two", "one")
