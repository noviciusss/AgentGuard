import logging

logger = logging.getLogger(__name__)


def perform_delete():
    return None


def perform_delete_tool():
    return None


def delete_tool():
    try:
        return perform_delete_tool()
    except Exception:
        logger.exception("delete failed")
        raise
