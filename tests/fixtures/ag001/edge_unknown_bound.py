from openai import OpenAI

client = OpenAI()
attempts = 0
limit = 3


def fetch(client, limit):
    while attempts < limit:  # expect: AG001
        try:
            client.responses.create(model="x", input="hello")
        except OSError:
            continue
