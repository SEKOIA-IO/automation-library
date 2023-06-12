import pytest
from aiobotocore.session import AioSession

from aws.client import AwsClient, AwsConfiguration


@pytest.fixture
def aws_configuration():
    return AwsConfiguration(aws_access_key_id="ACCESS_KEY", aws_secret_access_key="SECRET_KEY", aws_region="us-east-1")


@pytest.mark.asyncio
async def test_aws_client_init(aws_configuration):
    """
    Test AwsClient initialization.

    Args:
        aws_configuration:
    """
    client = AwsClient(aws_configuration)

    assert client._configuration == aws_configuration


@pytest.mark.asyncio
async def test_aws_client_get_session(aws_configuration):
    """
    Test AwsClient get_session init.

    Args:
        aws_configuration:
    """
    client = AwsClient(aws_configuration)

    session = client.get_session

    assert isinstance(session, AioSession)
