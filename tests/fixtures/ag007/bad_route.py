from langgraph.graph import StateGraph


def choose_route(state):
    return "next"


builder = StateGraph(dict)
builder.add_node("router", lambda state: state)
builder.add_conditional_edges("router", choose_route)  # expect: AG007
