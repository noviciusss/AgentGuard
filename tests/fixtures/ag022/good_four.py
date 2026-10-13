def typed_command(value):
    return {"action": value}


def dispatch(value):
    return value


dispatch(typed_command("safe"))
