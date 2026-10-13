def active():
    return True


def run(state):
    while active():
        state["messages"].append("message")  # expect: AG011
