from openai import OpenAI

client = OpenAI(timeout=10)
client.responses.create(model="model-2025-01-01", input="hello")
