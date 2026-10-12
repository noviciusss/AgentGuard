import requests


def fetch():
    for _ in range(3):
        requests.get("https://example.com")
