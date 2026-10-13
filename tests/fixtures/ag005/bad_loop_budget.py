from openai import OpenAI

client = OpenAI(timeout=30)
while True:
    client.responses.create(model="gpt-4", input="hello")  # expect: AG005
