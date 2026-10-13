from langgraph.graph import START, StateGraph

builder = StateGraph(dict)


def start(state):
    return state


def next_node(state):
    return state


builder.add_node("start", start)
builder.add_node("next", next_node)
builder.add_edge(START, "start")
builder.add_edge("start", "next")
