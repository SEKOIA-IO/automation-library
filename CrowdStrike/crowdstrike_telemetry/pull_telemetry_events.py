"""Contains connector, configuration and module."""

from typing import AsyncGenerator

import orjson
from aws_helpers.utils import AsyncReader
from connectors.s3 import AbstractAwsS3QueuedConnector, AwsS3QueuedConfiguration

from .metrics import DISCARDED_EVENTS

EXCLUDED_EVENT_ACTIONS = [
    "SensorHeartbeat",
    "ConfigStateUpdate",
    "ErrorEvent",
    "FalconServiceStatus",
    "CurrentSystemTags",
    "BillingInfo",
    "ChannelActive",
    "IdpDcPerfReport",
    "ProvisioningChannelVersionRequired",
    "ChannelVersionRequired",
    "SensorSelfDiagnosticTelemetry",
    "SystemCapacity",
    "MobilePowerStats",
    "DeliverRulesEngineResultsToCloud",
    "NeighborListIP4",
    "NeighborListIP6",
    "AgentConnect",
    "AgentOnline",
    "ResourceUtilization",
]


class CrowdStrikeTelemetryConnector(AbstractAwsS3QueuedConnector):
    """Implementation of CrowdStrikeTelemetryConnector."""

    name = "CrowdStrikeTelemetryConnector"
    configuration: AwsS3QueuedConfiguration

    async def _parse_content(self, stream: AsyncReader) -> AsyncGenerator[str, None]:
        """
        Parse content from S3 bucket.

        Args:
            stream: AsyncReader

        Returns:
             Generator:
        """
        records: AsyncGenerator[bytes, None] = (line.rstrip(b"\n") async for line in stream)

        async for record in records:
            if len(record) > 0:  # pragma: no cover
                try:
                    json_record = orjson.loads(record)
                    if (
                        json_record.get("event_simpleName") is None
                        or json_record.get("event_simpleName") in EXCLUDED_EVENT_ACTIONS
                    ):
                        DISCARDED_EVENTS.labels(intake_key=self.configuration.intake_key).inc()
                        continue

                    yield record.decode("utf-8")
                except Exception as e:
                    self.log(message=f"Failed to parse a record: {str(e)}", level="warning")
