"""Test abstract AWS connector."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError, EndpointConnectionError

from connectors import ENDPOINT_MAX_FAILURES, AbstractAwsConnector, AbstractAwsConnectorConfiguration, AwsModule
from connectors.s3.provider import AwsAccountProvider


def test_abstract_aws_connector(aws_module: AwsModule, symphony_storage: Path, intake_key: str):
    """
    Test abstract AWS connector.

    Args:
        aws_module: AwsModule
    """
    connector = AbstractAwsConnector(module=aws_module, data_path=symphony_storage)
    connector.configuration = AbstractAwsConnectorConfiguration(intake_key=intake_key)

    assert isinstance(connector, AwsAccountProvider)


@pytest.fixture
def connector(aws_module: AwsModule, symphony_storage: Path, intake_key: str) -> AbstractAwsConnector:
    connector = AbstractAwsConnector(module=aws_module, data_path=symphony_storage)
    connector.configuration = AbstractAwsConnectorConfiguration(intake_key=intake_key)
    # logging an exception posts it to the playbook run: not available in tests
    connector.log_exception = MagicMock()  # type: ignore[method-assign]
    return connector


def test_handle_error_stops_on_fatal_error(connector: AbstractAwsConnector):
    error = ClientError({"Error": {"Code": "AccessDenied"}}, "ReceiveMessage")

    with patch.object(connector, "stop") as stop, patch("connectors.time.sleep") as sleep:
        connector._handle_error(error)

    stop.assert_called_once()
    sleep.assert_not_called()


def test_handle_error_retries_other_errors(connector: AbstractAwsConnector):
    with patch.object(connector, "stop") as stop, patch("connectors.time.sleep") as sleep:
        connector._handle_error(ValueError("boom"))

    stop.assert_not_called()
    sleep.assert_not_called()


def test_handle_error_retries_unreachable_endpoint_before_stopping(connector: AbstractAwsConnector):
    error = EndpointConnectionError(endpoint_url="https://sqs.test.amazonaws.com/")

    with patch.object(connector, "stop") as stop, patch("connectors.time.sleep") as sleep:
        for _ in range(ENDPOINT_MAX_FAILURES - 1):
            connector._handle_error(error)

        stop.assert_not_called()
        assert sleep.call_count == ENDPOINT_MAX_FAILURES - 1

        connector._handle_error(error)

    stop.assert_called_once()


def test_handle_error_counts_consecutive_endpoint_failures(connector: AbstractAwsConnector):
    error = EndpointConnectionError(endpoint_url="https://sqs.test.amazonaws.com/")

    with patch.object(connector, "stop") as stop, patch("connectors.time.sleep"):
        for _ in range(ENDPOINT_MAX_FAILURES - 1):
            connector._handle_error(error)
        connector._handle_error(ValueError("another error resets the count"))
        connector._handle_error(error)

    stop.assert_not_called()
