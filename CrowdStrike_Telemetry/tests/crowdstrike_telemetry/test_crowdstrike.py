"""Tests for CrowdStrike Telemetry connector."""
import json
from unittest.mock import patch

import pytest

from crowdstrike_telemetry.crowdstrike import (
    CrowdStrikeTelemetryConfig,
    CrowdStrikeTelemetryConnector,
    CrowdStrikeTelemetryModule,
)


@pytest.fixture
def crowdstrike_connector(session_faker) -> CrowdStrikeTelemetryConnector:
    """
    Create CrowdStrikeTelemetryConnector instance.

    Args:
        session_faker: Faker

    Returns:
        CrowdStrikeTelemetryConnector:
    """
    config = CrowdStrikeTelemetryConfig(
        aws_access_key_id=session_faker.word(),
        aws_secret_access_key=session_faker.word(),
        queue_name=session_faker.word(),
        aws_region=session_faker.word(),
        intake_key=session_faker.word(),
        chunk_size=session_faker.random.randint(1, 10),
        frequency=session_faker.random.randint(0, 20),
        delete_consumed_messages=True,
        is_fifo=False,
    )

    module = CrowdStrikeTelemetryModule()
    module.configuration = config

    return CrowdStrikeTelemetryConnector(module)


@pytest.mark.asyncio
async def test_process_s3_file(crowdstrike_connector, session_faker):
    """
    Test process_s3_file method.

    Args:
        crowdstrike_connector: CrowdStrikeTelemetryConnector
        session_faker: Faker
    """
    key = session_faker.file_path(depth=2, extension="json")
    expected = [
        {"data": session_faker.sentence()},
        {"data": session_faker.sentence()},
    ]

    with patch.object(crowdstrike_connector.s3_wrapper, "read_key") as mock_read_key:
        mock_read_key.return_value.__aenter__.return_value = json.dumps(expected).encode("utf-8")

        result = await crowdstrike_connector.process_s3_file(key)

        assert result == expected
        mock_read_key.assert_called_once_with(key, None)
