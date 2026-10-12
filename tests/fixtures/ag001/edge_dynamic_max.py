from openai import OpenAI

limit = object()
client = OpenAI(max_retries=limit)
