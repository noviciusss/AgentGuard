from concurrent.futures import ThreadPoolExecutor
from threading import Lock

shared = {}
lock = Lock()


def worker(value):
    with lock:
        shared["value"] = value


with ThreadPoolExecutor() as pool:
    pool.submit(worker, 1)
