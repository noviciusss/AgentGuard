def delete_file_tool(idempotency_key):
    return None


def load_key():
    return "request"


for _ in range(2):
    delete_file_tool(idempotency_key=load_key())
