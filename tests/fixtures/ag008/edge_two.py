def perform_tool():
    return None


def lookup_tool():
    try:
        return perform_tool()
    except LookupError:
        return None
