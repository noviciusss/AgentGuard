from langgraph.graph import START, StateGraph


def entry(state):
    return state


def detached(state):
    return state


builder = StateGraph(dict)
builder.add_node("entry", entry)
builder.add_node("detached", detached)  # expect: AG006
builder.add_edge(START, "entry")
