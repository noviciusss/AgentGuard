from langgraph.graph import START, StateGraph


def start(state):
    return state


def next_node(state):
    return state


builder = StateGraph(dict)
builder.add_node("start", start)
builder.add_node("next", next_node)
builder.add_edge(START, "start")
builder.add_edge("start", "next")
