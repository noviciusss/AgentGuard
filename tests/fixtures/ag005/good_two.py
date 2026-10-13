from openai import OpenAI

client = OpenAI(timeout=10)
for _ in range(2):
    client.responses.create(model="gpt-4", input="hello", max_tokens=64)
