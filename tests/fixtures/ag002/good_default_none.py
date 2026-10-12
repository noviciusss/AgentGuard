from concurrent.futures import ThreadPoolExecutor


def worker(value, cache=None):
    cache = {} if cache is None else cache
    return cache.setdefault(value, value)


with ThreadPoolExecutor() as pool:
    pool.submit(worker, "x")
