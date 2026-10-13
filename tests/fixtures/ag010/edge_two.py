from openai import OpenAI


def load_model():
    return "gpt-4"


client = OpenAI(timeout=10)
client.responses.create(model=load_model(), input="hello")
