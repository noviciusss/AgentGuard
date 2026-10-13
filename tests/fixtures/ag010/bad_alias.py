from openai import OpenAI

client = OpenAI(timeout=30)
client.responses.create(model="latest", input="hello")  # expect: AG010
