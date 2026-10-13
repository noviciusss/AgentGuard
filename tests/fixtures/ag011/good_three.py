def active():
    return True


def run(state):
    while active():
        state["messages"] = state["messages"][-10:]
