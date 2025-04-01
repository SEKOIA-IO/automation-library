"""All available connectors for this module."""

import asyncio
import time
from abc import ABCMeta
from functools import cached_property
from typing import Any, Optional

from pydantic.v1 import BaseModel, Field
from sekoia_automation.aio.connector import AsyncConnector
from sekoia_automation.aio.helpers.aws.client import AwsClient, AwsConfiguration
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration
from sekoia_automation.module import Module

from .metrics import EVENTS_LAG, FORWARD_EVENTS_DURATION, MESSAGES_AGE, OUTCOMING_EVENTS


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

    async def next_batch(self) -> tuple[int, list[int]]:
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

                    batch_result: tuple[int, list[int]] = loop.run_until_complete(self.next_batch())
                    message_count, messages_timestamp = batch_result

                    # compute the duration of the batch
                    processing_end = time.time()
                    batch_duration = processing_end - processing_start

                    OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(message_count)
                    FORWARD_EVENTS_DURATION.labels(intake_key=self.configuration.intake_key).observe(
                        processing_end - processing_start
                    )

                    if message_count > 0:
                        self.log(message="Pushed {0} records".format(message_count), level="info")

                        # Identify delay between message timestamp ( when it was pushed to sqs )
                        # and current timestamp ( when it was processed )
                        messages_age = [
                            int(processing_end - message_timestamp / 1000) for message_timestamp in messages_timestamp
                        ]
                        current_lag = min(messages_age)

                        for age in messages_age:
                            MESSAGES_AGE.labels(intake_key=self.configuration.intake_key).observe(age)
                    else:
                        self.log(message="No records to forward", level="info")
                        MESSAGES_AGE.labels(intake_key=self.configuration.intake_key).observe(0)

                    # report the current lag
                    EVENTS_LAG.labels(intake_key=self.configuration.intake_key).set(current_lag)

                    # compute the remaining sleeping time. If greater than 0 and no messages were fetched, sleep
                    delta_sleep = self.configuration.frequency - batch_duration
                    if message_count == 0 and delta_sleep > 0:
                        self.log(message=f"Next batch in the future. Waiting {delta_sleep} seconds", level="info")
                        time.sleep(delta_sleep)

            except Exception as e:
                self.log_exception(e)

    def stop(self, *args: Any, **kwargs: Optional[Any]) -> None:  # pragma: no cover
        """
        Stop the connector
        """
        super(Connector, self).stop(*args, **kwargs)
