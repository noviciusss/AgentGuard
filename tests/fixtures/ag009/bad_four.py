def charge_payment_tool():
    return None


def retrying():
    return True


while retrying():
    charge_payment_tool()  # expect: AG009
