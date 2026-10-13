def SystemMessage(**kwargs):
    return kwargs


def HumanMessage(**kwargs):
    return kwargs


def run():
    user = input("prompt")
    SystemMessage(system_prompt="fixed policy")
    HumanMessage(content=user)
