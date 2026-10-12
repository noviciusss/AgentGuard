from concurrent.futures import ThreadPoolExecutor

shared = {"value": 1}


def worker():
    return shared["value"]


with ThreadPoolExecutor() as pool:
    pool.submit(worker)
