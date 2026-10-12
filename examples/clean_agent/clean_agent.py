"""A bounded agent with explicit timeouts and isolated task state."""

from concurrent.futures import ThreadPoolExecutor

import requests


def fetch_status() -> object:
    return requests.get("https://example.com", timeout=10)


def worker(value: str) -> str:
    return value.upper()


def run_agent() -> list[str]:
    values = ["first", "second"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(worker, values))
    for _ in range(2):
        fetch_status()
    return results
