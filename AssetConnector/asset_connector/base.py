import os
import time
import sentry_sdk
from pydantic import BaseModel

import requests
from requests import Response
from tenacity import Retrying, stop_after_delay, wait_exponential

from abc import abstractmethod
from collections.abc import Generator
from functools import cached_property
from os.path import join as urljoin

from .models import (
    DefaultAssetConnectorConfiguration,
    AssetObject,
    AssetList,
)

from sekoia_automation.trigger import Trigger
from sekoia_automation.exceptions import TriggerConfigurationError
from sekoia_automation.utils import get_annotation_for, get_as_model


class AssetConnector(Trigger):
    """
    Base class for all asset connectors.

    Asset connectors are used to collect data from an asset and send it to the Sekoia.io platform.
    """

    CONNECTOR_CONFIGURATION_FILE_NAME = "connector_configuration"
    PRODUCTION_BASE_URL = "https://api.sekoia.io"
    ASSET_BATCH_SIZE = 1000

    configuration: DefaultAssetConnectorConfiguration

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @property
    def connector_name(self) -> str:
        """
        Get connector name.

        Returns:
            str:
        """
        return self.__class__.__name__

    @property  # type: ignore[override, no-redef]
    def configuration(self) -> DefaultAssetConnectorConfiguration:
        """
        Get the module configuration.
        Returns:
            DefaultAssetConnectorConfiguration: Connector configuration
        """
        if self._configuration is None:
            try:
                self.configuration = self.module.load_config(self.CONNECTOR_CONFIGURATION_FILE_NAME, "json")
            except FileNotFoundError:
                return super().configuration  # type: ignore[return-value]
        return self._configuration  # type: ignore[return-value]

    @configuration.setter
    def configuration(self, configuration: dict) -> None:
        """
        Set the module configuration.

        Args:
            configuration: dict
        """
        try:
            self._configuration = get_as_model(get_annotation_for(self.__class__, "configuration"), configuration)
        except Exception as e:
            raise TriggerConfigurationError(str(e))

        if isinstance(self._configuration, BaseModel):
            sentry_sdk.set_context(self.CONNECTOR_CONFIGURATION_FILE_NAME, self._configuration.model_dump())

    @property
    def batch_size(self) -> int:
        """
        Get the batch size for the os env.

        Returns:
            int: Batch size
        """
        return int(os.getenv("ASSET_CONNECTOR_BATCH_SIZE", self.ASSET_BATCH_SIZE))

    @property
    def production_base_url(self) -> str:
        """
        Get the production base URL for os env.

        Returns:
            str: Production base URL
        """
        return os.getenv("ASSET_CONNECTOR_PRODUCTION_BASE_URL", self.PRODUCTION_BASE_URL)

    @property
    def frequency(self) -> int:
        """
        Get the frequency for the connector.

        Returns:
            str: Frequency
        """
        if frequency := os.getenv("ASSET_CONNECTOR_FREQUENCY"):
            return int(frequency)
        return self.configuration.frequency

    def _retry(self):
        return Retrying(
            stop=stop_after_delay(3600),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            reraise=True,
        )

    @cached_property
    def _http_session(self) -> requests.Session:
        return requests.Session()

    @cached_property
    def http_header(self) -> dict[str, str]:
        """
        Get the headers for the connector.

        Returns:
            dict: Headers
        """
        return {
            "Authorization": f"Bearer {self.configuration.api_key}",
            "Content-Type": "application/json",
        }

    def handle_api_error(self, error_code: int) -> str:
        error = {
            400: "Invalid request format",
            401: "Unauthorized access",
            404: "Connector not found",
        }
        return error.get(error_code, "An unknown error occurred")

    def post_assets_to_api(self, assets: list[dict[str, str]], asset_connector_api_url: str) -> dict[str, str] | None:
        """
        Post assets to the Sekoia.io asset connector API.
        Args:
            assets (AssetList): List of assets to post.
            asset_connector_api_url (str): URL of the asset connector API.
        Returns:
            dict[str, str] | None: Response from the API or None if an error occurred.
        """

        request_body = {
            "assets": assets,
        }

        try:
            for attempt in self._retry():
                with attempt:
                    res: Response = self._http_session.post(
                        asset_connector_api_url,
                        json=request_body,
                        timeout=30,
                    )
        except requests.Timeout as ex:
            self.log_exception(
                ex,
                message=f"Timeout while pushing assets to Sekoia.io asset connector API",
            )
            return None

        if res.status_code != 200:
            error_message = self.handle_api_error(res.status_code)
            self.log(
                message=f"Error while pushing assets to Sekoia.io: {error_message}",
                level="error",
            )
            return None

        self.log(
            message=f"Successfully posted {len(assets)} assets to Sekoia.io asset connector API",
            level="info",
        )
        return res.json()

    def push_assets_to_sekoia(self, assets: list[dict[str, str]]) -> None:
        """
        Push assets to the Sekoia.io asset connector API.
        Args:
            assets (AssetList): List of assets to push.
        Returns:
            None: If the assets were successfully pushed.
        """

        if not assets:
            return

        asset_connector_uuid = self.connector_configuration_uuid
        if sekoia_base_url := self.configuration.sekoia_base_url:
            batch_api = urljoin(sekoia_base_url, "api/v1/asset-connectors")
        else:
            batch_api = urljoin(self.production_base_url, "api/v1/asset-connectors")

        url = urljoin(batch_api, asset_connector_uuid)

        self.log(
            message=f"Pushing {len(assets)} assets to Sekoia.io asset connector API at {url}",
            level="info",
        )

        response = self.post_assets_to_api(
            assets=assets,
            asset_connector_api_url=url,
        )

        if response is None:
            self.log(
                message=f"Failed to push assets to Sekoia.io asset connector API at {url}",
                level="error",
            )
            return

    @abstractmethod
    def get_assets(self) -> Generator[dict[str, str], None, None]:
        """
        Get assets from the connector.
        Yields:
            AssetObject: Asset object.
        """
        raise NotImplementedError("This method should be implemented in a subclass")

    def asset_fetch_cycle(self) -> None:
        """
        Fetch assets from the connector and push them to Sekoia.io.
        This method is called in a loop until the connector is stopped.
        """

        self.log(
            message=f"Starting a new asset fetch cycle for connector {self.connector_name}",
            level="info",
        )

        # save the starting time processing
        processing_start = time.time()

        assets = []
        total_number_of_assets = 0
        for asset in self.get_assets():
            try:
                AssetObject(**asset)  # type: ignore[arg-type]
            except Exception as e:
                self.log_exception(
                    None,
                    message=f"Asset {asset} is not an instance of AssetObject",
                )
                continue

            assets.append(asset)
            total_number_of_assets += 1

            if len(assets) >= self.batch_size:
                self.push_assets_to_sekoia(assets)
                assets = []

        if assets:
            self.push_assets_to_sekoia(assets)

        # save the end time processing
        processing_end = time.time()
        processing_time = processing_end - processing_start

        # Compute the remaining sleeping time.
        # If greater than 0 and no messages where fetched, pause the connector
        delta_sleep = self.frequency - processing_time
        if total_number_of_assets == 0 and delta_sleep > 0:
            self.log(message=f"Next run in the future. Waiting {delta_sleep} seconds")

            time.sleep(delta_sleep)

    def run(self) -> None:
        while self.running:
            try:
                self.asset_fetch_cycle()
            except Exception as e:
                self.log_exception(
                    e,
                    message=f"Error while running asset connector {self.connector_name}",
                )
