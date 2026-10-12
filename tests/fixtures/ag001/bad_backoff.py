import backoff
import requests


@backoff.on_exception(backoff.expo, OSError)  # expect: AG001
def fetch():
    return requests.get("https://example.com")
