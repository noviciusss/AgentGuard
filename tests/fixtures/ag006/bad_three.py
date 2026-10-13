from langgraph.graph import START, StateGraph


def start(state):
    return state


def unused(state):
    return state


builder = StateGraph(dict)
builder.add_node("start", start)
builder.add_node("unused", unused)  # expect: AG006
builder.add_edge(START, "start")
