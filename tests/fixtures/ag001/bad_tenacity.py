from openai import OpenAI
from tenacity import retry

client = OpenAI()


@retry  # expect: AG001
def ask(client):
    return client.responses.create(model="x", input="hello")
