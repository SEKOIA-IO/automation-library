"""Contains connector, configuration and module."""
import asyncio
import time
from typing import Any, List

import orjson
from loguru import logger
from pydantic import HttpUrl
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration
from sekoia_automation.module import Module

from client.http_client import TrellixHttpClient


class TrellixConfig(DefaultConnectorConfiguration):
    """Configuration for TrellixConnector."""

    client_id: str
    client_secret: str
    api_key: str
    delay: int = 60
    auth_url: HttpUrl = HttpUrl("https://iam.mcafee-cloud.com/iam/v1.1", scheme="https")
    base_url: HttpUrl = HttpUrl("https://api.manage.trellix.com", scheme="https")


class TrellixModule(Module):
    """TrellixModule."""

    configuration: TrellixConfig


class TrellixEdrConnector(Connector):
    """TrellixEdrConnector class to work with EDR events."""

    name = "TrellixEdrConnector"

    module: TrellixModule

    @property
    def trellix_http_client(self) -> TrellixHttpClient:
        """
        Get configured Trellix http client.

        Returns:
            TrellixHttpClient:
        """
        return TrellixHttpClient(
            client_id=self.module.configuration.client_id,
            client_secret=self.module.configuration.client_secret,
            api_key=self.module.configuration.api_key,
            auth_url=self.module.configuration.auth_url,
            base_url=self.module.configuration.base_url,
        )

    async def get_trellix_edr_events(self) -> List[Any]:
        """
        Process trellix edr events.

        Returns:
            List[Any]:
        """
        events = await self.trellix_http_client.get_edr_investigations()

        if events:
            await asyncio.to_thread(
                self.push_events_to_intakes,
                events=[orjson.dumps(event).decode("utf-8") for event in events],
                sync=True,
            )

        return events

    def run(self) -> None:
        """Runs TrellixEdr."""
        loop = asyncio.get_event_loop()
        try:
            while self.running:
                loop.run_until_complete(self.get_trellix_edr_events())
                time.sleep(self.module.configuration.delay)

        except Exception as e:
            logger.error("Error while running TrellixEdr: {error}", error=e)

        finally:
            loop.close()
