"""Contains connector, configuration and module."""

import asyncio
import time
from typing import Any, Optional

import orjson
from loguru import logger
from pydantic import BaseModel, Field
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration
from sekoia_automation.module import Module
from sekoia_automation.storage import PersistentJSON

from client.graphql_client import CatoGraphQLClient

from .metrics import EVENTS_LAG, FORWARD_EVENTS_DURATION, OUTCOMING_EVENTS


class CatoModuleConfig(BaseModel):
    """Configuration for CatoModule."""

    api_key: str = Field(secret=True)
    account_id: str


class CatoModule(Module):
    """CatoModule."""

    configuration: CatoModuleConfig


class CatoSaseConnectorConfig(DefaultConnectorConfiguration):
    """CatoSaseConnector configuration."""


class CatoSaseConnector(Connector):
    """CatoSaseConnector class to work with cato events."""

    name = "CatoSaseConnector"

    module: CatoModule
    configuration: CatoSaseConnectorConfig

    _cato_client: CatoGraphQLClient | None = None

    def __init__(self, *args: Any, **kwargs: Optional[Any]) -> None:
        """Init CatoSaseConnector."""

        super().__init__(*args, **kwargs)
        self.context = PersistentJSON("context.json", self._data_path)

    @property
    def latest_events_feed_id(self) -> str | None:
        """
        Get last event id.

        More details you can find in the documentation ( look into `eventsFeed Marker` section):
        https://support.catonetworks.com/hc/en-us/articles/360019839477#heading-3

        Returns:
            str | None:
        """
        with self.context as cache:
            result: str | None = cache.get("latest_events_feed_id")

            return result

    @property
    def cato_client(self) -> CatoGraphQLClient:
        """
        Get CatoGraphQLClient client.

        Returns:
            CatoGraphQLClient:
        """
        if self._cato_client is not None:
            return self._cato_client

        self._cato_client = CatoGraphQLClient(
            api_key=self.module.configuration.api_key,
            account_id=self.module.configuration.account_id,
        )

        return self._cato_client

    async def _push_events(self, events: list[str]) -> list[str]:
        """
        Push events to intakes.

        Simple wrapper over `self.push_events_to_intakes` to run it async.

        Args:
            events: list[str]

        Returns:
            list[str]:
        """
        logger.info("Pushing {count} events to intake", count=len(events))

        return await asyncio.to_thread(
            self.push_events_to_intakes,
            events=events,
            sync=True,
        )

    async def get_cato_events(self) -> list[str]:
        """
        Process cato events.

        Returns:
            list[str]: list of event ids
        """
        events = await self.cato_client.load_events_feed(self.latest_events_feed_id)

        new_latest_events_id = events.marker
        if new_latest_events_id:
            with self.context as cache:
                cache["latest_events_feed_id"] = new_latest_events_id

        result = []
        for account in events.accounts:
            for event in account.records:
                single_event = {"event_time": event.time, **event.fieldsMap}

                result.append(orjson.dumps(single_event).decode("utf-8"))

        return await self._push_events(result)

    def run(self) -> None:  # pragma: no cover
        """Runs Cato Sase."""
        previous_processing_end = None

        while self.running:
            try:
                loop = asyncio.get_event_loop()

                while self.running:
                    processing_start = time.time()
                    if previous_processing_end is not None:
                        EVENTS_LAG.labels(intake_key=self.configuration.intake_key).set(
                            processing_start - previous_processing_end
                        )

                    message_ids: list[str] = loop.run_until_complete(self.get_cato_events())
                    processing_end = time.time()
                    OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(message_ids))

                    log_message = "No records to forward"
                    if len(message_ids) > 0:
                        log_message = "Pushed {0} records".format(len(message_ids))

                    logger.info(log_message)
                    self.log(message=log_message, level="info")
                    logger.info(log_message)
                    logger.info(
                        "Processing took {processing_time} seconds",
                        processing_time=(processing_end - processing_start),
                    )

                    FORWARD_EVENTS_DURATION.labels(intake_key=self.configuration.intake_key).observe(
                        processing_end - processing_start
                    )

                    previous_processing_end = processing_end

            except Exception as e:
                logger.error("Error while running Cato SASE: {error}", error=e)
