from functools import cached_property
from collections.abc import Generator

from datetime import timedelta, datetime
from typing import Any
from urllib.parse import urljoin
from dateutil.parser import isoparse

from sekoia_automation.checkpoint import CheckpointDatetime

from .helper import handle_uri, map_os_type
from ..models import DeviceOCSFModel, Metadata, OperatingSystem, Device
from ..base import AssetConnector
from .client import HarfanglabApiClient
from .models import HarfanglabAssetConnectorModuleConfiguration


class HarfanglabAssetConnector(AssetConnector):
    module: HarfanglabAssetConnectorModuleConfiguration

    AGENT_ENDPOINT: str = "/api/data/endpoint/Agent"
    DEVICE_ORDERING_FIELD: str = "firstseen"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.cursor = CheckpointDatetime(
            path=self._data_path, start_at=timedelta(hours=24), ignore_older_than=timedelta(days=7)
        )
        self.from_date = self.cursor.offset

    @cached_property
    def client(self) -> HarfanglabApiClient:
        return HarfanglabApiClient(
            api_token=self.module.configuration.api_key,
        )

    @cached_property
    def base_url(self) -> str:
        """
        Get the base URL for the asset connector.

        Returns:
            str: The base URL.
        """
        return handle_uri(self.module.configuration.base_url)

    @cached_property
    def limit(self) -> int:
        """
        Get the limit for the number of assets to retrieve.

        Returns:
            int: The limit.
        """
        return 1000

    def extract_timestamp(self, asset: dict[str, Any]) -> datetime:
        return isoparse(asset["firstseen"])

    def map_fields(self, asset: dict[str, Any]) -> DeviceOCSFModel:

        metadata_object = Metadata(product="Harfanglab EDR", version="1.5.0")

        os_object = OperatingSystem(
            name=asset.get("osproducttype"), type=asset.get("ostype"), type_id=map_os_type(asset.get("ostype"))
        )

        device_object = Device(
            type_id=2,
            type="Desktop",
            uid=asset["id"],
            os=os_object,
            hostname=asset["hostname"],
        )

        return DeviceOCSFModel(
            activity_id=2,
            activity_name="Collect",
            category_name="Discovery",
            category_uid=5,
            class_name="Asset",
            class_uid=5001,
            type_name="Software Inventory Info: Collect",
            type_uid=500102,
            time=self.extract_timestamp(asset).timestamp(),
            metadata=metadata_object,
            device=device_object,
        )

    def __fetch_devices(self, from_date: datetime) -> Generator[list[dict[str, Any]], None, None]:
        devices_url = urljoin(self.base_url, self.AGENT_ENDPOINT)
        offset = 0

        params = {
            "ordering": self.DEVICE_ORDERING_FIELD,
            "firstseen": from_date.isoformat(),
            "limit": self.limit,
            "offset": offset,
        }

        device_response = self.client.get(devices_url, params=params)
        device_response.raise_for_status()

        while self.running:
            devices = device_response.json()

            # Check if there are no devices or if the count is zero
            # This is to handle the case where there are no devices returned
            if not devices or devices.get("count") == 0:
                return

            yield devices.get("results", [])

            next_page = devices.get("next")

            # If there is no next page, break the loop
            if not next_page:
                return

            # Update the offset for the next request
            offset += self.limit
            params["offset"] = offset

            device_response = self.client.get(next_page, params=params)
            device_response.raise_for_status()

    def next_list_devices(self) -> Generator[list[dict[str, Any]], None, None]:
        most_recent_date_seen = self.from_date

        for devices in self.__fetch_devices(from_date=most_recent_date_seen):
            if devices:
                last_event = max(devices, key=self.extract_timestamp)
                last_event_datetime = self.extract_timestamp(last_event)

                # Update the most recent date seen if the last event is more recent
                if last_event_datetime > most_recent_date_seen:
                    most_recent_date_seen = last_event_datetime + timedelta(microseconds=1)

                yield devices

        # Update the cursor with the most recent date seen
        if most_recent_date_seen > self.from_date:
            self.cursor.offset = most_recent_date_seen
            self.from_date = most_recent_date_seen

    def get_assets(self) -> Generator[DeviceOCSFModel, None, None]:
        for devices in self.next_list_devices():
            for device in devices:
                mapped_device: DeviceOCSFModel = self.map_fields(device)
                yield mapped_device
