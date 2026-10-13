from langgraph.graph import START, StateGraph

builder = StateGraph(dict)


def only(state):
    return state


builder.add_node("only", only)
builder.add_edge(START, "only")
