"""Test abstract AWS connector."""

from pathlib import Path
from unittest.mock import MagicMock

from connectors import AbstractAwsConnector, AbstractAwsConnectorConfiguration, AwsModule
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


def test_abstract_aws_connector_run_with_empty_timestamps(
    aws_module: AwsModule, symphony_storage: Path, intake_key: str
):
    """Ensure run loop handles successful batches without source timestamps."""

    class DummyConnector(AbstractAwsConnector):
        async def next_batch(self) -> tuple[int, list[int]]:
            self.stop()
            return 1, []

    connector = DummyConnector(module=aws_module, data_path=symphony_storage)
    connector.configuration = AbstractAwsConnectorConfiguration(intake_key=intake_key, frequency=0)
    connector.log = MagicMock()
    connector.log_exception = MagicMock()

    initial_heartbeat = connector._last_heartbeat
    connector.run()

    assert connector.log_exception.call_count == 0
    assert connector._last_heartbeat >= initial_heartbeat
