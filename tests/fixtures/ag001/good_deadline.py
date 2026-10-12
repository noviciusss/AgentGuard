import time

import requests


def fetch(deadline):
    while time.monotonic() < deadline:
        requests.get("https://example.com")
