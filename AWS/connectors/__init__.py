"""All available connectors for this module."""
import asyncio
import time
from abc import ABCMeta
from functools import cached_property

from pydantic import BaseModel, Field
from sekoia_automation.aio.connector import AsyncConnector
from sekoia_automation.aio.helpers.aws.client import AwsClient, AwsConfiguration
from sekoia_automation.connector import DefaultConnectorConfiguration
from sekoia_automation.module import Module

from .metrics import EVENTS_LAG, FORWARD_EVENTS_DURATION, OUTCOMING_EVENTS


class AwsModuleConfiguration(BaseModel):
    """The configuration of the AWS module."""

    aws_access_key: str = Field(..., description="The identifier of the access key")
    aws_secret_access_key: str = Field(secret=True, description="The secret associated to the access key")
    aws_region_name: str = Field(..., description="The area hosting the AWS resources")


class AwsModule(Module):
    """The AWS module."""

    configuration: AwsModuleConfiguration


class AbstractAwsConnectorConfiguration(DefaultConnectorConfiguration):
    """The abstract connector configuration."""

    frequency: int = 60


class AbstractAwsConnector(AsyncConnector, metaclass=ABCMeta):
    """The abstract connector."""

    module: AwsModule
    configuration: AbstractAwsConnectorConfiguration

    @cached_property
    def aws_client(self) -> AwsClient:
        """
        Base implementation of AWS client.

        AwsClient contains `get_client` method with correct initialization.

        Returns:
            AwsClientT:
        """
        config = AwsConfiguration(
            aws_access_key_id=self.module.configuration.aws_access_key,
            aws_secret_access_key=self.module.configuration.aws_secret_access_key,
            aws_region=self.module.configuration.aws_region_name,
        )

        return AwsClient(config)

    async def next_batch(self) -> tuple[list[str], list[int]]:
        """
        Get next batch of messages.

        Contains main logic of the connector.

        Returns:
            tuple[list[str], int]:
        """
        raise NotImplementedError("next_batch method must be implemented")

    def run(self) -> None:  # pragma: no cover
        """Run the connector."""
        while self.running:
            try:
                loop = asyncio.get_event_loop()

                while self.running:
                    processing_start = time.time()

                    batch_result: tuple[list[str], list[int]] = loop.run_until_complete(self.next_batch())
                    message_ids, messages_timestamp = batch_result

                    # Identify delay between message timestamp ( when it was pushed to sqs )
                    # and current timestamp ( when it was processed )
                    processing_end = time.time()
                    for message_timestamp in messages_timestamp:
                        EVENTS_LAG.labels(intake_key=self.configuration.intake_key).observe(
                            processing_end - message_timestamp
                        )

                    OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(message_ids))

                    log_message = "No records to forward"
                    if len(message_ids) > 0:
                        log_message = "Pushed {0} records".format(len(message_ids))

                    self.log(message=log_message, level="info")

                    FORWARD_EVENTS_DURATION.labels(intake_key=self.configuration.intake_key).observe(
                        processing_end - processing_start
                    )

                    time.sleep(self.configuration.frequency)

            except Exception as e:
                self.log_exception(e)
