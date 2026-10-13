def perform_tool():
    return None


def delete_tool():
    try:
        return perform_tool()
    except Exception:
        return {"deleted": False}
