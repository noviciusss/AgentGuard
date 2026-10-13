from openai import OpenAI

client = OpenAI(timeout=30)


def load_model():
    return "gpt-4"


client.responses.create(model=load_model(), input="hello")
