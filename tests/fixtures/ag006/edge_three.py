from langgraph.graph import START, StateGraph


def start(state):
    return state


builder = StateGraph(dict)
builder.add_node("start", start)
builder.add_edge(START, "start")
