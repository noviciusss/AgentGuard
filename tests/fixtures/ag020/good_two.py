def SystemMessage(**kwargs):
    return kwargs


def UserMessage(**kwargs):
    return kwargs


def run():
    query = input("query")
    SystemMessage(system_prompt="fixed")
    UserMessage(content=query)
