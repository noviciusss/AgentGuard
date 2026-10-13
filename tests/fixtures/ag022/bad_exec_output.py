import subprocess

from openai import OpenAI

client = OpenAI(timeout=30)
output = client.responses.create(model="gpt-4-2024-08-06", input="hello")
subprocess.run(output)  # expect: AG022
