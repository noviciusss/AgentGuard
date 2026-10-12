from tenacity import retry, stop_after_attempt


@retry(stop=stop_after_attempt(3))
def ask(client):
    return client.invoke("hello")
