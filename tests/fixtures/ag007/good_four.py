from langgraph.graph import END, StateGraph


def route(state):
    return "done"


builder = StateGraph(dict)
builder.add_node("router", route)
builder.add_conditional_edges("router", route, {"done": END})
