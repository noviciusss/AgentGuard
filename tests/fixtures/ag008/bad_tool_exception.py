def perform_delete():
    return None


def perform_delete_tool():
    return None


def delete_tool():
    try:
        return perform_delete_tool()
    except Exception:  # expect: AG008
        pass
