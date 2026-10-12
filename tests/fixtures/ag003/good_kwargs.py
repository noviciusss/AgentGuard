import requests

options = {"timeout": 10}
requests.get("https://example.com", **options)
