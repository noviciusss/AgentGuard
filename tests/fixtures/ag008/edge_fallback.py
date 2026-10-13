def perform_lookup():
    return None


def perform_lookup_tool():
    return None


def lookup_tool():
    try:
        return perform_lookup_tool()
    except LookupError:
        return {"missing": True}
