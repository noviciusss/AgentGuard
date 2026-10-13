import logging

logger = logging.getLogger(__name__)


def perform_tool():
    return None


def send_tool():
    try:
        return perform_tool()
    except Exception:
        logger.exception("send failed")
        raise
