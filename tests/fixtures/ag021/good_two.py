path = "/tmp/file"


def human_approved(value):
    return True


def delete_file_tool(value):
    return value


if human_approved(path):
    delete_file_tool(path)
