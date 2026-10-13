def active():
    return True


def summarize(value):
    return value


def run(state):
    while active():
        state["messages"] = summarize(state["messages"])
