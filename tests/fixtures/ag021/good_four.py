value = "command"


def human_confirmed(item):
    return True


def shell_exec_tool(item):
    return item


if human_confirmed(value):
    shell_exec_tool(value)
