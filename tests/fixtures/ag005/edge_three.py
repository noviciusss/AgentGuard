from openai import OpenAI

request_options = {}

client = OpenAI(timeout=10)
for _ in range(2):
    client.responses.create(model="gpt-4", input="hello", **request_options)
