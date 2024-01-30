"""Config tests."""

import pytest
from pydantic import ValidationError

from logger.config import LoggingConfig


@pytest.mark.asyncio
async def test_config_default_values():
    """Test config default init."""
    config = LoggingConfig()

    assert config.log_lvl == "INFO"
    assert config.log_file == "logs/{time:YYYY-MM-DD}.log"
    assert config.log_rotation == "00:00"
    assert config.log_retention == "1 month"
    assert config.log_compression == "zip"
    assert config.log_queue
    assert config.json_logs is False
    assert (
        config.loguru_format
        == "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <5}</level> | <level>{message}</level>"
    )


@pytest.mark.asyncio
async def test_config_assemble_log_lvl():
    """Test config assemble log lvl."""
    valid_log_lvl = "debug"
    config = LoggingConfig(log_lvl=valid_log_lvl)
    assert config.log_lvl == valid_log_lvl.upper()

    invalid_log_lvl = "invalid"

    try:
        LoggingConfig(log_lvl=invalid_log_lvl)

    except ValidationError as e:
        assert "Incorrect log lvl variable" in str(e)
