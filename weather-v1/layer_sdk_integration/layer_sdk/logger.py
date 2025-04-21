"""The logger module for the Layer SDK."""

import sys
import logging


def setup_logger(name: str, level: int = logging.DEBUG) -> logging.Logger:
    """Set up the logger.

    Args:
        name (str): The logger name
        level (int, optional): The logging level. Defaults to logging.INFO.

    Returns:
        logging.Logger: The logger
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    handler = logging.StreamHandler(sys.stdout)

    # e.g. [2023-10-05 14:12:26 - layer_minus_sdk._base_client:818 - DEBUG]
    # HTTP Request: POST http://127.0.0.1:4010/foo/bar "200 OK"
    formatter = logging.Formatter(
        "[%(asctime)s - %(name)s:%(lineno)d - %(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)

    # Add the handler to the logger
    logger.addHandler(handler)

    return logger


logger: logging.Logger = setup_logger("layer-sdk")
_urllib3_logger: logging.Logger = setup_logger("urllib3.connectionpool")
