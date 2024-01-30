"""Formatters tests."""

import pytest
from faker import Faker

from logger.formatters import format_record


@pytest.mark.asyncio
async def test_formatted_record_non_empty(session_faker: Faker):
    """
    Test format record to correct string.

    Args:
        session_faker: Faker
    """
    log_str = session_faker.sentence(nb_words=10)

    str_format = "".join(
        [
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | ",
            "<level>{level: <5}</level> | ",
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - ",
            "<level>{message}</level>",
        ],
    )

    expected_result = "".join(
        [str_format, "\n<level>{extra[payload]}</level>{exception}\n"],
    )

    assert expected_result == format_record(
        {"extra": {"payload": {"data": log_str}}},
        str_format,
    )


@pytest.mark.asyncio()
async def test_formatted_record_empty():
    """Test format record to correct string if payload is empty."""
    str_format = "".join(
        [
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | ",
            "<level>{level: <5}</level> | ",
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - ",
            "<level>{message}</level>",
        ],
    )

    expected_result = "".join(
        [str_format, "{exception}\n"],
    )

    assert expected_result == format_record({"extra": {}}, str_format)
