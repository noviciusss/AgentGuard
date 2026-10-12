from concurrent.futures import ThreadPoolExecutor


def worker(value, cache={}):  # noqa: B006  # deliberate mutable-default fixture
    return cache.setdefault(value, value)


with ThreadPoolExecutor() as pool:
    pool.submit(worker, "x")  # expect: AG002
