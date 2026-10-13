def perform_tool():
    return None


def read_tool():
    try:
        return perform_tool()
    except OSError:
        raise
