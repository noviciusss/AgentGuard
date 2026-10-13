from openai import OpenAI


def ready():
    return True


client = OpenAI(timeout=10)
while ready():
    client.responses.create(model="gpt-4", input="hello", max_tokens=64)
