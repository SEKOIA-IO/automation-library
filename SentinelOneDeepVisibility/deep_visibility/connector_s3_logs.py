import json
from collections.abc import AsyncGenerator
from typing import BinaryIO

from connectors.s3 import AbstractAwsS3QueuedConnector, AwsS3QueuedConfiguration
from deep_visibility.metrics import DISCARDED_EVENTS

EXCLUDED_EVENT_TYPES = [
    "File Modification",
    "File Scan",
    "Open Remote Process Handle",
    "Duplicate Process Handle",
    "Not Reported",
]


class DeepVisibilityConnector(AbstractAwsS3QueuedConnector):
    """Implementation of DeepVisibilityConnector."""

    configuration: AwsS3QueuedConfiguration
    name = "DeepVisibility AWS S3 Logs"

    async def _parse_content(self, stream: BinaryIO) -> AsyncGenerator[str, None]:
        """
        Parse content from S3 bucket.

        Args:
            stream: BinaryIO

        Returns:
             Generator:
        """
        content = await stream.read()

        for record in content.decode("utf-8").split("\n"):
            if len(record) > 0:
                try:
                    json_record = json.loads(record)
                    # Exclude events with no category defined or a group category
                    if "event.category" not in json_record or json_record["event.category"] == "group":
                        DISCARDED_EVENTS.labels(intake_key=self.configuration.intake_key).inc()
                        continue
                    # Exclude specific event types
                    if "event.type" in json_record and json_record["event.type"] in EXCLUDED_EVENT_TYPES:
                        DISCARDED_EVENTS.labels(intake_key=self.configuration.intake_key).inc()
                        continue

                    yield record
                except:
                    pass
