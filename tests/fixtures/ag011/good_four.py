items = []


def run(state):
    for item in items:
        state["history"].append(item)
        state["history"] = state["history"][-20:]
