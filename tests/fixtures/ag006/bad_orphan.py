from langgraph.graph import START, StateGraph

builder = StateGraph(dict)


def start(state):
    return state


def orphan(state):
    return state


builder.add_node("start", start)
builder.add_node("orphan", orphan)  # expect: AG006
builder.add_edge(START, "start")
