def run(state):
    while True:
        state["messages"].append("message")
        state["messages"] = state["messages"][-10:]
