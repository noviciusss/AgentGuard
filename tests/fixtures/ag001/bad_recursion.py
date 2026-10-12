from openai import OpenAI

client = OpenAI()


def retry_call(client):
    try:
        return client.responses.create(model="x", input="hello")
    except OSError:
        return retry_call(client)  # expect: AG001
