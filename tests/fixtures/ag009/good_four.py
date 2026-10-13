def charge_payment_tool(idempotency_key):
    return None


for _ in range(2):
    charge_payment_tool(idempotency_key="request")
