"""Test abstract AWS connector."""
from sekoia_automation.aio.helpers.aws.client import AwsClient
from sekoia_automation.connector import DefaultConnectorConfiguration

from connectors import AbstractAwsConnector, AwsModule


def test_abstract_aws_connector(aws_module: AwsModule, intake_key: str):
    """
    Test abstract AWS connector.

    Args:
        aws_module: AwsModule
    """
    connector = AbstractAwsConnector()
    connector.module = aws_module
    connector.configuration = DefaultConnectorConfiguration(intake_key=intake_key)

    assert isinstance(connector.aws_client, AwsClient)
