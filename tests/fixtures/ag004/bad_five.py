from langgraph.graph import START, StateGraph


def check(state):
    return state


def retry(state):
    return state


builder = StateGraph(dict)  # expect: AG004
builder.add_node("check", check)
builder.add_node("retry", retry)
builder.add_edge(START, "check")
builder.add_edge("check", "retry")
builder.add_edge("retry", "check")
