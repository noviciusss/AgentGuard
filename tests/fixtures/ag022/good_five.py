def model_output():
    return "value"


def parse_schema(value):
    return type("Result", (), {"action": value})()


def dispatch(value):
    return value


result = parse_schema(model_output())
dispatch(result.action)
