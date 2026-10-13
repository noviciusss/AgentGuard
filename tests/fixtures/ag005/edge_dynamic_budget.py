from openai import OpenAI


def get_budget():
    return 64


client = OpenAI(timeout=30)
budget = get_budget()
for _ in range(2):
    client.responses.create(model="gpt-4", input="hello", max_tokens=budget)
