def SystemMessage(**kwargs):
    return kwargs


def UserMessage(**kwargs):
    return kwargs


def run(tool_output):
    SystemMessage(system_prompt="fixed")
    UserMessage(content=tool_output)
