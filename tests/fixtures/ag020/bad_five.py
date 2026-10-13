def SystemMessage(**kwargs):
    return kwargs


def run(prompt):
    SystemMessage(system_prompt=prompt)  # expect: AG020
