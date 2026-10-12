import requests


def fetch():
    while True:  # expect: AG001
        try:
            requests.get("https://example.com")
        except OSError:
            continue
