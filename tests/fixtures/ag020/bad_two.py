def SystemMessage(**kwargs):
    return kwargs


def run():
    query = input("query")
    SystemMessage(system_prompt=query)  # expect: AG020
