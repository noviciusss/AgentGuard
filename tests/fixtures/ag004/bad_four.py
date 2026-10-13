from langgraph.graph import START, StateGraph


def review(state):
    return state


def revise(state):
    return state


builder = StateGraph(dict)  # expect: AG004
builder.add_node("review", review)
builder.add_node("revise", revise)
builder.add_edge(START, "review")
builder.add_edge("review", "revise")
builder.add_edge("revise", "review")
