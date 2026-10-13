from langgraph.graph import START, StateGraph


def first(state):
    return state


builder = StateGraph(dict)
builder.add_node("first", first)
builder.add_edge(START, "first")
