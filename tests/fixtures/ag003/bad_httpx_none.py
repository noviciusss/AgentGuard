import httpx

httpx.get("https://example.com", timeout=None)  # expect: AG003
