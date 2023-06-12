"""Base InterceptHandler class."""

import logging

from loguru import logger


class InterceptHandler(logging.Handler):
    """
    Default handler.

    See docs https://loguru.readthedocs.io/en/stable/overview.html#entirely-compatible-with-standard-logging
    """

    def emit(self, record: logging.LogRecord) -> None:
        """
        Get corresponding Loguru level if it exists.

        Args:
            record: LogRecord

        Raises:
            ValueError: in case if any errors during logging raises
        """
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelname

        # Find caller from where originated the logged message
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            if frame.f_back is None:
                raise ValueError("f_back error while logger")

            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level,
            record.getMessage(),
        )
