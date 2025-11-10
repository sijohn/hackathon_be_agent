import logging
import sys

def get_logger(name: str) -> logging.Logger:
    """Initializes a logger with a default handler and formatter."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.propagate = False  # Prevent duplicate logs in parent loggers

    # If the logger already has handlers, don't add another one.
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger
