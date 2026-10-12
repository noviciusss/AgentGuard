from openai import OpenAI

client = OpenAI()  # expect: AG003
client.responses.create(model="gpt-test", input="hello")  # expect: AG003
