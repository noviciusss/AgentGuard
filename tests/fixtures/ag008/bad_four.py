def perform_tool():
    return None


def delete_tool():
    try:
        return perform_tool()
    except Exception:  # expect: AG008
        pass
