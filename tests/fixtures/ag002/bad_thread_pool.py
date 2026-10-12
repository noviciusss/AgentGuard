from concurrent.futures import ThreadPoolExecutor

shared = {}


def worker(value):
    shared["value"] = value


with ThreadPoolExecutor() as pool:
    pool.submit(worker, 1)  # expect: AG002
