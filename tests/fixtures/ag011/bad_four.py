def run(state):
    while True:
        state["messages"].extend(["message"])  # expect: AG011
