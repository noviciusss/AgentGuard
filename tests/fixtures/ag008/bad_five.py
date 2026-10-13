def perform_tool():
    return None


def email_tool():
    try:
        return perform_tool()
    except Exception:  # expect: AG008
        pass
