from openai import OpenAI


def ready():
    return True


client = OpenAI(timeout=10)
while ready():
    client.responses.create(model="gpt-4", input="hello")  # expect: AG005
