"""A deliberately unsafe plain-Python agent used in the README demo.

The source is analyzed statically and is not run by the example tests.
"""

from concurrent.futures import ThreadPoolExecutor

import requests

shared_results: dict[str, str] = {}


def worker(value: str) -> None:
    shared_results["last"] = value


def retry_request() -> object:
    while True:
        try:
            return requests.get("https://example.com")
        except OSError:
            continue


def run_agent() -> None:
    with ThreadPoolExecutor(max_workers=2) as pool:
        pool.submit(worker, "first")
        pool.submit(worker, "second")
