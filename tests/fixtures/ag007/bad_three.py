from langgraph.graph import StateGraph


def route(state):
    return "missing"


builder = StateGraph(dict)
builder.add_node("router", route)
builder.add_conditional_edges("router", route)  # expect: AG007
