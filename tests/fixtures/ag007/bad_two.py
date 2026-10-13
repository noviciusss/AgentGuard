from langgraph.graph import StateGraph


def choose(state):
    return "next"


builder = StateGraph(dict)
builder.add_node("router", choose)
builder.add_conditional_edges("router", choose)  # expect: AG007
