"""Tests related to logging."""

import logging
from logging import LogRecord

import pytest

from logger.config import init_logging
from logger.handlers import InterceptHandler


@pytest.fixture
def logger_handler() -> InterceptHandler:
    """
    InterceptHandler fixture.
    Returns:
        InterceptHandler:
    """
    return InterceptHandler()


def test_logging_emit_with_existing_loguru_level(logger_handler):
    """
    Test logging emit with existing loguru level.
    Args:
        logger_handler: InterceptHandler
    """
    record = LogRecord("name", 30, "pathname", 10, "message", (), None)
    logger_handler.emit(record)

    try:
        record1 = LogRecord("name", 100500, "pathname", 10, "message", (), None)
        logger_handler.emit(record1)
    except ValueError as e:
        assert str(e) == "Level 'Level 100500' does not exist"


def test_logging_log_message():
    """
    Test logging emit with existing loguru level.
    """
    init_logging()

    assert logging.root.handlers != []
