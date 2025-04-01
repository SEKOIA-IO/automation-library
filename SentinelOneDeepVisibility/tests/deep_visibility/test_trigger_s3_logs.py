"""Tests related to AwsS3LogsTrigger."""

from pathlib import Path

import pytest
from faker import Faker

from deep_visibility.connector_s3_logs import DeepVisibilityConnector
from deep_visibility import SentinelOneDeepVisibilityModule, SentinelOneDeepVisibilityConfiguration

from tests.helpers import async_list, async_temporary_file


@pytest.fixture
def test_data() -> bytes:
    return """

{"message":"EPP Device Collected","dataSource.vendor":"SentinelOne","timestamp":"2024-04-30T09:06:28.629Z"}
{"src.process.parent.isStorylineRoot":false,"event.category":"indicators","indicator.category":"InfoStealer","event.type":"Behavioral Indicators"}
{"src.process.parent.isStorylineRoot":false,"event.category":"group","src.process.parent.image.sha1":"973efc4a04e2d26ae8777fa86fb7ac19fcd8c4e4"}
{"src.process.parent.isStorylineRoot":false,"event.category":"file","indicator.category":"InfoStealer","event.type":"File Scan"}
2 111111111111 eni-0a479835a7588c9ca 188.114.116.1 172.31.39.167 123 44789 17 1 76 1645469669 1645469724 ACCEPT OK

""".encode(
        "utf-8"
    )


@pytest.fixture
def connector(
    deepvisibility_module: SentinelOneDeepVisibilityModule,
    symphony_storage: Path,
    deepvisibility_configuration: SentinelOneDeepVisibilityConfiguration,
) -> DeepVisibilityConnector:
    """
    Create a connector.

    Args:
        aws_module: AwsModule
        symphony_storage: Path
        deepvisibility_configuration: SentinelOneDeepVisibilityConfiguration

    Returns:
        DeepVisibilityConnector:
    """
    connector = DeepVisibilityConnector(module=deepvisibility_module, data_path=symphony_storage)

    connector.module = deepvisibility_module
    connector.configuration = deepvisibility_configuration

    return connector


@pytest.mark.asyncio
async def test_aws_s3_logs_trigger_parse_data(connector: DeepVisibilityConnector, test_data: bytes):
    """
    Test DeepVisibilityConnector `_parse_data`.

    Args:
        connector: DeepVisibilityConnector
        test_data: bytes
    """

    async with async_temporary_file(test_data) as f:
        assert await async_list(connector._parse_content(f)) == [
            [line for line in test_data.decode("utf-8").split("\n") if line != ""][1]
        ]


@pytest.mark.asyncio
async def test_aws_s3_logs_trigger_parse_empty_data(connector: DeepVisibilityConnector):
    async with async_temporary_file(b"") as f:
        assert await async_list(connector._parse_content(f)) == []
