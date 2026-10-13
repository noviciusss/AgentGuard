from langgraph.graph import START, StateGraph


def start(state):
    return state


def orphan(state):
    return state


builder = StateGraph(dict)
builder.add_node("start", start)
builder.add_node("orphan", orphan)  # expect: AG006
builder.add_edge(START, "start")
