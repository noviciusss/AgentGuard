def send_email_tool(idempotency_key):
    return None


for _ in range(2):
    send_email_tool(idempotency_key="request")
