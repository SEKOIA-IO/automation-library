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
                    current_lag: int = 0

                    batch_result: tuple[list[str], list[int]] = loop.run_until_complete(self.next_batch())
                    message_ids, messages_timestamp = batch_result

                    # compute the duration of the batch
                    processing_end = time.time()
                    batch_duration = processing_end - processing_start

                    OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(message_ids))
                    FORWARD_EVENTS_DURATION.labels(intake_key=self.configuration.intake_key).observe(
                        processing_end - processing_start
                    )

                    if len(message_ids) > 0:
                        self.log(message="Pushed {0} records".format(len(message_ids)), level="info")

                        # Identify delay between message timestamp ( when it was pushed to sqs )
                        # and current timestamp ( when it was processed )
                        max_message_timestamp = max(messages_timestamp)
                        current_lag = int(processing_end - max_message_timestamp / 1000)
                    else:
                        self.log(message="No records to forward", level="info")

                    # report the current lag
                    EVENTS_LAG.labels(intake_key=self.configuration.intake_key).set(current_lag)

                    # compute the remaining sleeping time. If greater than 0 and no messages were fetched, sleep
                    delta_sleep = self.configuration.frequency - batch_duration
                    if len(message_ids) == 0 and delta_sleep > 0:
                        self.log(message=f"Next batch in the future. Waiting {delta_sleep} seconds", level="info")
                        time.sleep(delta_sleep)

            except Exception as e:
                self.log_exception(e)
