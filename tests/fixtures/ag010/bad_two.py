from openai import OpenAI

client = OpenAI(timeout=10)
client.responses.create(model="gpt-4", input="hello")  # expect: AG010
