"""Contains AwsSqsMessagesTrigger."""
from functools import cached_property

import orjson
from sekoia_automation.connector import DefaultConnectorConfiguration

from aws_helpers.sqs_wrapper import SqsConfiguration, SqsWrapper
from connectors import AbstractAwsConnector


class AwsSqsMessagesTriggerConfiguration(DefaultConnectorConfiguration):
    """Contains configuration for AwsSqsMessagesTrigger."""

    frequency: int = 60
    sqs_frequency: int = 10
    chunk_size: int = 10000
    delete_consumed_messages: bool = False
    queue_name: str


class AwsSqsMessagesTrigger(AbstractAwsConnector):
    """Implementation of AWS SQS Messages trigger."""

    name = "AWS SQS Messages"
    configuration: AwsSqsMessagesTriggerConfiguration

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

    async def next_batch(self) -> list[str]:
        """
        Get next batch of messages.

        Contains main logic of the connector.

        Returns:
            list[str]:
        """
        async with self.sqs_wrapper.receive_messages(max_messages=10) as messages:
            records = []
            for message in messages:
                try:
                    # Records is a list of strings
                    records.extend(orjson.loads(message).get("Records", []))
                except ValueError as e:
                    self.log_exception(e, message=f"Invalid JSON in message.\nInvalid message is: {message}")

            self.log(message=f"Forwarding {len(records)} messages", level="info")

            result: list[str] = await self.push_data_to_intakes(events=records)

            return result
