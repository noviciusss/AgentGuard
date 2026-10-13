def SystemMessage(**kwargs):
    return kwargs


def run():
    user = input("prompt")
    SystemMessage(system_prompt=user)  # expect: AG020
