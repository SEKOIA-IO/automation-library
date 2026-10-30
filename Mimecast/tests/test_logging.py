from unittest.mock import Mock, patch

from mimecast_modules.logging import get_logger


def test_get_logger_delegates_to_structlog() -> None:
    expected_logger = Mock()

    with patch("mimecast_modules.logging.structlog.get_logger", return_value=expected_logger) as get_logger_mock:
        logger = get_logger("mimecast")

    assert logger is expected_logger
    get_logger_mock.assert_called_once_with("mimecast")
