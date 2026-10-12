from concurrent.futures import ThreadPoolExecutor


def worker(value):
    local = []
    local.append(value)
    return local


with ThreadPoolExecutor() as pool:
    pool.submit(worker, 1)
