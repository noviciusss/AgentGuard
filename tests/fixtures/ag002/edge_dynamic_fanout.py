shared = {}


def worker(value):
    shared["value"] = value


def submit(pool, function):
    pool.submit(function, 1)
