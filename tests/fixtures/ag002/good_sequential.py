shared = []


def worker(value):
    shared.append(value)


worker(1)
