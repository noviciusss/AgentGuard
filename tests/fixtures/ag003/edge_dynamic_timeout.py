import requests

timeout = object()
requests.get("https://example.com", timeout=timeout)
