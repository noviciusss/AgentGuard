items = []


def run(state):
    for item in items:
        state["history"].append(item)  # expect: AG011
