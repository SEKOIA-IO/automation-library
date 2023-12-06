"""Test abstract AWS connector."""

from pathlib import Path
from unittest.mock import patch
import asyncio

from sekoia_automation.aio.helpers.aws.client import AwsClient
from sekoia_automation.connector import DefaultConnectorConfiguration
import pytest

from connectors import AbstractAwsConnector, AwsModule


def test_abstract_aws_connector(aws_module: AwsModule, symphony_storage: Path, intake_key: str):
    """
    Test abstract AWS connector.

    Args:
        aws_module: AwsModule
    """
    connector = AbstractAwsConnector(module=aws_module, data_path=symphony_storage)
    connector.configuration = DefaultConnectorConfiguration(intake_key=intake_key)

    assert isinstance(connector.aws_client, AwsClient)


class FakeAWSConnector(AbstractAwsConnector):
    def __init__(self, module, data_path, messages_ids: list, messages_timestamp: list):
        super().__init__(module=module, data_path=data_path)
        self.messages_ids = messages_ids
        self.messages_timestamp = messages_timestamp

    async def next_batch(self) -> tuple[list[str], list[int]]:
        """
        Get next batch of messages.

        Contains main logic of the connector.

        Returns:
            tuple[list[str], int]:
        """
        return ( self.messages_ids, self.messages_timestamp)


def test_connector_run_should_pause(aws_module: AwsModule, symphony_storage: Path, intake_key: str):
    """
    Test abstract AWS connector.

    Args:
        aws_module: AwsModule
    """
    connector = FakeAWSConnector(
        module=aws_module,
        data_path=symphony_storage,
        messages_ids=[],
        messages_timestamp=[]
    )
    connector.configuration = DefaultConnectorConfiguration(intake_key=intake_key)
    event_loop = asyncio.get_event_loop()

    with patch("connectors.time") as mock_time, patch("connectors.AbstractAwsConnector.running", side_effect=[True, True, False]):
        batch_duration = 16  # the batch lasts 16 seconds
        start_time = 1701862800.0
        end_time = start_time + batch_duration
        mock_time.time.side_effect = [start_time, end_time]

        connector._next_batch(event_loop)

        mock_time.sleep.assert_called_once_with(44)


def test_connector_run_should_not_pause(aws_module: AwsModule, symphony_storage: Path, intake_key: str):
    """
    Test abstract AWS connector.

    Args:
        aws_module: AwsModule
    """
    connector = FakeAWSConnector(
        module=aws_module,
        data_path=symphony_storage,
        messages_ids=["f5ca74e3-13ea-4a9b-875d-6c79c33e9aaa", "e0381838-84da-47e2-9a57-a560d72ed0eb", "b718257b-1cec-4905-bf4a-cee2e9f27bcf"],
        messages_timestamp=[1701819000, 1701862822, 1701845760]
    )
    connector.configuration = DefaultConnectorConfiguration(intake_key=intake_key)
    event_loop = asyncio.get_event_loop()

    with patch("connectors.time") as mock_time, patch("connectors.AbstractAwsConnector.running", side_effect=[True, True, False]):
        batch_duration = 73  # the batch lasts 73 seconds
        start_time = 1701862800.0
        end_time = start_time + batch_duration
        mock_time.time.side_effect = [start_time, end_time]

        connector._next_batch(event_loop)

        assert mock_time.sleep.call_count == 0


def test_connector_run_with_lag_should_not_pause(aws_module: AwsModule, symphony_storage: Path, intake_key: str):
    """
    Test abstract AWS connector.

    Args:
        aws_module: AwsModule
    """
    connector = FakeAWSConnector(
        module=aws_module,
        data_path=symphony_storage,
        messages_ids=["f5ca74e3-13ea-4a9b-875d-6c79c33e9aaa", "e0381838-84da-47e2-9a57-a560d72ed0eb", "b718257b-1cec-4905-bf4a-cee2e9f27bcf"],
        messages_timestamp=[1701819000, 1701862822, 1701845760]
    )
    connector.configuration = DefaultConnectorConfiguration(intake_key=intake_key)
    event_loop = asyncio.get_event_loop()

    with patch("connectors.time") as mock_time, patch("connectors.AbstractAwsConnector.running", side_effect=[True, True, False]):
        batch_duration = 16  # the batch lasts 16 seconds
        start_time = 1701845760.0
        end_time = start_time + batch_duration
        mock_time.time.side_effect = [start_time, end_time]

        connector._next_batch(event_loop)

        assert mock_time.sleep.call_count == 0
