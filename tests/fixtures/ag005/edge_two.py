from openai import OpenAI


def load_budget():
    return 64


client = OpenAI(timeout=10)
budget = load_budget()
for _ in range(2):
    client.responses.create(model="gpt-4", input="hello", max_tokens=budget)
