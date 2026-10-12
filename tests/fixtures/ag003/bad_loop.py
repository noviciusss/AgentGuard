import requests

for _ in range(2):
    requests.get("https://example.com")  # expect: AG003
