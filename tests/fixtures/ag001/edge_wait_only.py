from openai import OpenAI
from tenacity import retry, wait_fixed

client = OpenAI()


@retry(wait=wait_fixed(1))  # expect: AG001
def ask(client):
    return client.responses.create(model="x", input="hello")
