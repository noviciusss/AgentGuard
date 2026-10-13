def active():
    return True


cache = {}


def run(state):
    while active():
        cache.update({"latest": "message"})
