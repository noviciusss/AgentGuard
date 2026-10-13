from openai import OpenAI

client = OpenAI(timeout=10)
client.responses.create(model="claude-3", input="hello")  # expect: AG010
