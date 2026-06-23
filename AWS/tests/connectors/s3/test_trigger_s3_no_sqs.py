from pathlib import Path

import pytest
from faker import Faker

from connectors import AwsModule
from connectors.s3.trigger_s3_logs_no_sqs import AwsS3LogsNoSqsConfiguration, AwsS3LogsNoSqsTrigger
from tests.helpers import async_list, async_temporary_file


@pytest.fixture
def test_data() -> bytes:
    return r"""2024-09-11 18:46:00","Active Directory User (adusername@example.net)","Active Directory User (adusername@example.net),WIN11-SNG01-Example","10.10.1.100","24.123.132.133","Allowed","1 (A)","NOERROR","domain-visited.com.","Software/Technology,Business Services,Allow List,Infrastructure and Content Delivery Networks,SaaS and B2B,Application","AD Users","AD Users,Anyconnect Roaming Client","","506165","","8234970"
"2024-09-11 18:46:00","Active Directory User (adusername@example.net)","Active Directory User (adusername@example.net),WIN11-SNG01-Example","10.10.1.100","24.123.132.133","Blocked","1 (A)","NOERROR","domain-visited.com.","Chat,Social Networking","AD Users","AD Users,Anyconnect Roaming Client","Social Networking","506165","","8234970"
""".encode(
        "utf-8"
    )


@pytest.fixture
def aws_s3_flowlogs_trigger_config(faker: Faker) -> AwsS3LogsNoSqsConfiguration:
    """
    Create a configuration.

    Args:
        faker: Faker

    Returns:
        AwsS3LogsConfiguration:
    """
    config = {
        "frequency": 60,
        "separator": "\n",
        "skip_first": 0,
        "ignore_comments": True,
        "bucket": "test-bucket",
        "prefix_filter": "123/dnslogs/",
        "intake_key": faker.word(),
    }

    return AwsS3LogsNoSqsConfiguration(**config)


@pytest.fixture
def connector(
    aws_module: AwsModule,
    symphony_storage: Path,
    aws_s3_flowlogs_trigger_config: AwsS3LogsNoSqsConfiguration,
) -> AwsS3LogsNoSqsTrigger:
    """
    Create a connector.

    Args:
        aws_module: AwsModule
        symphony_storage: Path
        aws_s3_flowlogs_trigger_config: AwsS3LogsNoSqsConfiguration

    Returns:
        AwsS3ParquetRecordsTrigger:
    """
    connector = AwsS3LogsNoSqsTrigger(module=aws_module, data_path=symphony_storage)

    connector.configuration = aws_s3_flowlogs_trigger_config

    return connector


@pytest.mark.asyncio
async def test_aws_s3_logs_trigger_parse_data(connector: AwsS3LogsNoSqsTrigger, test_data: bytes):
    """
    Test AwsS3LogsNoSqsTrigger `_parse_data`.

    Args:
        connector: AwsS3LogsNoSqsTrigger
        test_data: bytes
    """

    async with async_temporary_file(test_data) as f:
        assert (
            await async_list(connector._parse_content(f))
            == [line for line in test_data.decode("utf-8").split("\n") if line != "" and not line.startswith("#")][
                connector.configuration.skip_first :
            ]
        )


@pytest.mark.asyncio
async def test_aws_s3_logs_trigger_parse_empty_data(connector: AwsS3LogsNoSqsTrigger):
    async with async_temporary_file(b"") as f:
        assert await async_list(connector._parse_content(f)) == []
