from openai import OpenAI

client = OpenAI(timeout=10)
client.responses.create(model="claude-3-2024-06-20", input="hello")
