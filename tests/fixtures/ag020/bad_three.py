def SystemMessage(**kwargs):
    return kwargs


def run():
    message = input("message")
    SystemMessage(system=message)  # expect: AG020
