message = "hello"


def human_approved(value):
    return True


def send_email_tool(value):
    return value


if human_approved(message):
    send_email_tool(message)
