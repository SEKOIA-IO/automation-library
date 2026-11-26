import importlib
import logging

import pytest

import netskope_modules.logging as netskope_logging


@pytest.fixture
def reload_logging(monkeypatch):
    def _reload(log_level: str | None):
        if log_level is None:
            monkeypatch.delenv("LOG_LEVEL", raising=False)
        else:
            monkeypatch.setenv("LOG_LEVEL", log_level)
        return importlib.reload(netskope_logging)

    yield _reload

    # Restore the default structlog configuration for the other tests
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    importlib.reload(netskope_logging)


@pytest.mark.parametrize(
    "log_level,expected_enabled,expected_disabled",
    [
        (None, logging.INFO, logging.DEBUG),
        (str(logging.ERROR), logging.ERROR, logging.WARNING),
    ],
)
def test_get_logger_respects_log_level(reload_logging, log_level, expected_enabled, expected_disabled):
    module = reload_logging(log_level)

    logger = module.get_logger("netskope").bind()

    assert logger.is_enabled_for(expected_enabled)
    assert not logger.is_enabled_for(expected_disabled)
