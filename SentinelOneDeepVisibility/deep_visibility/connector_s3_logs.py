import os
from collections.abc import AsyncGenerator
from typing import Any, Optional
from functools import cached_property

import orjson
from aws_helpers.utils import AsyncReader
from connectors.s3 import AbstractAwsS3QueuedConnector, AwsS3QueuedConfiguration
from connectors.s3.provider import AwsAccountProvider
from deep_visibility.metrics import DISCARDED_EVENTS

EXCLUDED_EVENT_TYPES = [
    "File Modification",
    "File Scan",
    "Open Remote Process Handle",
    "Duplicate Process Handle",
    "Not Reported",
]


class DeepVisibilityConnector(AbstractAwsS3QueuedConnector, AwsAccountProvider):
    """Implementation of DeepVisibilityConnector."""

    configuration: AwsS3QueuedConfiguration
    name = "DeepVisibility AWS S3 Logs"

    def __init__(self, *args: Any, **kwargs: Optional[Any]) -> None:
        """Init DeepVisibilityConnector."""

        super().__init__(*args, **kwargs)
        self.sqs_visibility_timeout = int(os.getenv("AWS_SQS_VISIBILITY_TIMEOUT", 300))

    @cached_property
    def scalability_labels(self) -> dict[str, str]:
        """Get scalability labels from module manifest."""
        labels = self.module.manifest.get("labels", {})
        scalable_horizontally = str(labels.get("scalable-horizontally", False)).lower()
        scalable_vertically = str(labels.get("scalable-vertically", False)).lower()
        return {
            "scalable-horizontally": scalable_horizontally,
            "scalable-vertically": scalable_vertically,
        }

    async def _parse_content(self, stream: AsyncReader) -> AsyncGenerator[str, None]:
        """
        Parse content from S3 bucket.

        Args:
            stream: AsyncReader

        Returns:
             Generator:
        """
        # Use the iterator protocol to read the stream line by line. Using readline() would uncompress the entire file in memory
        records = (line.rstrip(b"\n") async for line in stream)

        async for record in records:
            if len(record) > 0:
                try:
                    json_record = orjson.loads(record)
                    # Exclude events with no category defined or a group category
                    if (
                        "event.category" not in json_record
                        or json_record["event.category"] == "group"
                    ):
                        DISCARDED_EVENTS.labels(
                            intake_key=self.configuration.intake_key,
                            **self.scalability_labels,
                        ).inc()
                        continue
                    # Exclude specific event types
                    if (
                        "event.type" in json_record
                        and json_record["event.type"] in EXCLUDED_EVENT_TYPES
                    ):
                        DISCARDED_EVENTS.labels(
                            intake_key=self.configuration.intake_key,
                            **self.scalability_labels,
                        ).inc()
                        continue

                    yield record.decode("utf-8")
                except Exception as e:
                    self.log(
                        message=f"Failed to parse a record: {str(e)}", level="warning"
                    )
