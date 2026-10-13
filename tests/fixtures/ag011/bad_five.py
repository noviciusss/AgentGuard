items = []


def run(state):
    for item in items:
        state["messages"].insert(0, item)  # expect: AG011
