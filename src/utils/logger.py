import logging


def setup_logger(name: str) -> logging.Logger:
    """Configure detailed CloudWatch logging."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    return logger
