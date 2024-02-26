"""All available connectors for this module."""

import asyncio
import time
from abc import ABCMeta
from functools import cached_property
from typing import Any, Callable

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

    # The number of records that connector should process at once.
    records_in_queue_per_batch: int = 10000


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
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.async_run())

    async def async_run(self) -> None:
        """Run the connector."""
        background_tasks = set()
        while self.running:
            try:
                processing_start = time.time()
                result = await self.next_batch()
                records, messages_timestamp = result
                if records:
                    task = asyncio.create_task(self.push_data_to_intakes(events=records))
                    background_tasks.add(task)
                    task.add_done_callback(
                        background_tasks.discard
                    )  # Remove the task from the one that must be awaited when exiting
                    task.add_done_callback(self.push_data_to_intakes_callback(processing_start, messages_timestamp))
                else:
                    self.log(message="No records to forward", level="info")
                    await asyncio.sleep(self.configuration.frequency)
            except Exception as e:
                self.log_exception(e)

        # Wait for all logs to be pushed before exiting
        await asyncio.gather(*background_tasks, return_exceptions=True)

    def push_data_to_intakes_callback(
        self, processing_start: float, messages_timestamp: list[int]
    ) -> Callable[[asyncio.Task[Any]], None]:
        """Callback to remove the task from the background tasks set."""

        def callback(task: asyncio.Task[Any]) -> None:
            """Callback to remove the task from the background tasks set."""
            message_ids = task.result()
            processing_end = time.time()
            for message_timestamp in messages_timestamp:
                EVENTS_LAG.labels(intake_key=self.configuration.intake_key).set(
                    processing_end - (message_timestamp / 1000)
                )

            OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(message_ids))
            FORWARD_EVENTS_DURATION.labels(intake_key=self.configuration.intake_key).observe(
                processing_end - processing_start
            )
            if len(message_ids) > 0:
                self.log(message="Pushed {0} records".format(len(message_ids)), level="info")

        return callback
