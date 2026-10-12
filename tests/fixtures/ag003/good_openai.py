from openai import OpenAI

client = OpenAI(timeout=30)
client.responses.create(model="gpt-test", input="hello")
