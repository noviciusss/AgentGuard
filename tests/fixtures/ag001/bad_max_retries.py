from openai import OpenAI

client = OpenAI(max_retries=11)  # expect: AG001
