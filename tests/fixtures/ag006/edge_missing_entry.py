from langgraph.graph import StateGraph

builder = StateGraph(dict)


def node(state):
    return state


builder.add_node("node", node)
