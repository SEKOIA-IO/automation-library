"""Test abstract AWS connector."""

from pathlib import Path

from sekoia_automation.aio.helpers.aws.client import AwsClient
from sekoia_automation.connector import DefaultConnectorConfiguration

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
