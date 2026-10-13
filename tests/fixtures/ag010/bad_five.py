from openai import OpenAI

client = OpenAI(timeout=10)
client.responses.create(model="default", input="hello")  # expect: AG010
