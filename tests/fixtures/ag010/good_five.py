from openai import OpenAI

client = OpenAI(timeout=10)
client.responses.create(model="provider-2024-12", input="hello")
