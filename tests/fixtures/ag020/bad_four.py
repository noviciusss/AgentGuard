def SystemMessage(**kwargs):
    return kwargs


def run(user_input):
    SystemMessage(system_prompt=user_input)  # expect: AG020
