from langgraph.graph import START, StateGraph


def entry(state):
    return state


def dead(state):
    return state


builder = StateGraph(dict)
builder.add_node("entry", entry)
builder.add_node("dead", dead)  # expect: AG006
builder.add_edge(START, "entry")
