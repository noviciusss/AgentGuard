from openai import OpenAI

client = OpenAI(timeout=30)
for _ in range(2):
    client.responses.create(model="gpt-4-2024-08-06", input="hello", max_tokens=64)
