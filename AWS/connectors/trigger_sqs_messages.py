"""Contains AwsSqsMessagesTrigger."""

import os
from functools import cached_property
from typing import Any, Optional

import orjson

from aws_helpers.sqs_wrapper import SqsConfiguration, SqsWrapper
from connectors import AbstractAwsConnector, AbstractAwsConnectorConfiguration


class AwsSqsMessagesTriggerConfiguration(AbstractAwsConnectorConfiguration):
    """Contains configuration for AwsSqsMessagesTrigger."""

    sqs_frequency: int = 10
    chunk_size: int = 10000
    delete_consumed_messages: bool = True
    queue_name: str


class AwsSqsMessagesTrigger(AbstractAwsConnector):
    """Implementation of AWS SQS Messages trigger."""

    name = "AWS SQS Messages"
    configuration: AwsSqsMessagesTriggerConfiguration

    def __init__(self, *args: Any, **kwargs: Optional[Any]) -> None:
        """Init AbstractAwsS3QueuedConnector."""

        super().__init__(*args, **kwargs)
        self.limit_of_events_to_push = int(os.getenv("AWS_BATCH_SIZE", 10000))
        self.sqs_max_messages = int(os.getenv("AWS_SQS_MAX_MESSAGES", 10))

    @cached_property
    def sqs_wrapper(self) -> SqsWrapper:
        """
        Get SQS wrapper.

        Returns:
            SqsWrapper:
        """
        config = SqsConfiguration(
            frequency=self.configuration.sqs_frequency,
            delete_consumed_messages=self.configuration.delete_consumed_messages,
            queue_name=self.configuration.queue_name,
            aws_access_key_id=self.module.configuration.aws_access_key,
            aws_secret_access_key=self.module.configuration.aws_secret_access_key,
            aws_region=self.module.configuration.aws_region_name,
        )

        return SqsWrapper(config)

    async def next_batch(self) -> tuple[int, list[int]]:
        """
        Get next batch of messages.

        Contains main logic of the connector.

        Returns:
            tuple[list[str], list[int]]:
        """
        records = []
        timestamps_to_log: list[int] = []

        continue_receiving = True
        while continue_receiving:
            async with self.sqs_wrapper.receive_messages(max_messages=self.sqs_max_messages) as messages:
                if not messages:
                    continue_receiving = False

                for data in messages:
                    message, message_timestamp = data

                    timestamps_to_log.append(message_timestamp)
                    try:
                        # Records is a list of strings
                        records.extend(orjson.loads(message).get("Records", []))
                    except ValueError as e:
                        self.log_exception(e, message=f"Invalid JSON in message.\nInvalid message is: {message}")

            if len(records) >= self.limit_of_events_to_push or not records:
                continue_receiving = False

        self.log(message=f"Forwarding {len(records)} messages", level="info")

        result: list[str] = await self.push_data_to_intakes(
            events=[orjson.dumps(record).decode("utf-8") for record in records],
        )

        return len(result), timestamps_to_log
