def SystemMessage(**kwargs):
    return kwargs


def UserMessage(**kwargs):
    return kwargs


def run(message):
    SystemMessage(system_prompt="fixed")
    UserMessage(content=message)
