amount = 10


def human_consented(value):
    return True


def charge_payment_tool(value):
    return value


if human_consented(amount):
    charge_payment_tool(amount)
