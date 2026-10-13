from langgraph.graph import START, StateGraph


def first(state):
    return state


def second(state):
    return state


builder = StateGraph(dict)
builder.add_node("first", first)
builder.add_node("second", second)
builder.add_edge(START, "first")
builder.add_edge("first", "second")
builder.add_edge("second", "first")
builder.compile(recursion_limit=5)
