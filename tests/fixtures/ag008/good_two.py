import logging

logger = logging.getLogger(__name__)


def perform_tool():
    return None


def write_tool():
    try:
        return perform_tool()
    except Exception:
        logger.exception("write failed")
        raise
