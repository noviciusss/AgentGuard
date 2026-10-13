def SystemMessage(**kwargs):
    return kwargs


def load_policy():
    return "fixed"


def run():
    SystemMessage(system_prompt=load_policy())
