from openai import OpenAI


class Connection:
    def execute(self, value):
        return value


client = OpenAI(timeout=10)
output = client.responses.create(model="gpt-4-2024-08-06", input="hello")
connection = Connection()
connection.execute(output)  # expect: AG022
