import backoff
import requests


@backoff.on_exception(backoff.expo, OSError, max_tries=3)
def fetch():
    return requests.get("https://example.com")
