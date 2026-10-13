def write_file_tool(idempotency_key):
    return None


for _ in range(2):
    write_file_tool(idempotency_key="request")
