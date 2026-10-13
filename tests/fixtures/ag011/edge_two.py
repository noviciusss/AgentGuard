def active():
    return True


def run(state):
    while active():
        state["messages"].append("message")
        state["messages"] = state["messages"][-10:]
