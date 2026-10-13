from openai import OpenAI


def attempts():
    return range(2)


client = OpenAI(timeout=10)
for _attempt in attempts():
    client.responses.create(model="gpt-4", input="hello")  # expect: AG005
