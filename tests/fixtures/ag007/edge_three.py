from langgraph.graph import END, StateGraph


def load_route():
    return "done"


def route(state):
    return load_route()


builder = StateGraph(dict)
builder.add_node("router", route)
builder.add_conditional_edges("router", route, {"done": END})
