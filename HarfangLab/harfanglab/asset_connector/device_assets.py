import tempfile
import uuid
from functools import cached_property
from collections.abc import Generator
from typing import Any, Union
from urllib.parse import urljoin

from dateutil.parser import isoparse
from datetime import timedelta, datetime

from sekoia_automation.asset_connector import AssetConnector
from sekoia_automation.asset_connector.models.ocsf.base import (
    Metadata,
    Product,
)
from sekoia_automation.asset_connector.models.ocsf.device import (
    DeviceOCSFModel,
    OperatingSystem,
    Device,
    OSTypeStr,
    DeviceTypeId,
    DeviceTypeStr,
    OSTypeId,
)
from sekoia_automation.storage import PersistentJSON

from harfanglab.helpers import handle_uri
from harfanglab.client import ApiClient


class HarfanglabAssetConnector(AssetConnector):

    AGENT_ENDPOINT: str = "/api/data/endpoint/Agent"
    DEVICE_ORDERING_FIELD: str = "firstseen"
    PRODUCT_NAME: str = "Harfanglab EDR"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Temporary path to store the context
        self.context_path = tempfile.gettempdir()
        tempfile_name = str(uuid.uuid4())
        self.context = PersistentJSON(tempfile_name, self.context_path)

    @property
    def most_recent_date_seen(self) -> str | None:
        with self.context as cache:
            most_recent_date_seen = cache.get("most_recent_date_seen", None)

            return most_recent_date_seen

    @cached_property
    def client(self) -> ApiClient:
        """
        Get the API client for the Harfanglab asset connector.
        This client is used to interact with the Harfanglab API.
        """
        return ApiClient(token=self.module.configuration["api_token"], instance_url=self.base_url)

    @cached_property
    def base_url(self) -> str:
        """
        Get the base URL for the asset connector.

        Returns:
            str: The base URL.
        """
        return handle_uri(self.module.configuration["url"])

    @cached_property
    def limit(self) -> int:
        """
        Get the limit for the number of assets to retrieve.

        Returns:
            int: The limit.
        """
        return 1000

    @staticmethod
    def extract_timestamp(asset: dict[str, Any]) -> datetime:
        """
        Extract the timestamp from the asset data and transform it to datetime.

        Returns:
            datetime: The extracted timestamp as a datetime object.
        """
        return isoparse(asset["firstseen"])

    @staticmethod
    def extract_os_type(os_type: str | None) -> str:
        """
        Extract the OS type from the asset data and map it.

        returns:
            str: The OS type of asset.
        """
        os_type_list = [member.name for member in OSTypeStr]
        os_type = os_type.strip().upper() if os_type else ""

        if not os_type:
            return "UNKNOWN"

        if os_type and os_type not in os_type_list:
            return "OTHER"

        return os_type

    def map_fields(self, asset: dict[str, Any]) -> DeviceOCSFModel:
        """
        Map the fields from the asset data to the OCSF Device model.

        return:
            DeviceOCSFModel: The mapped OCSF Device model.
        """
        self.log(f"Mapping fields for asset: {asset.get('hostname', 'Unknown Hostname')}", level="debug")

        product = Product(name=self.PRODUCT_NAME, version="24.12")
        metadata = Metadata(product=product, version="1.5.0")
        os_type = self.extract_os_type(asset.get("ostype"))
        os_obj = OperatingSystem(name=asset.get("osproducttype"), type=OSTypeStr[os_type], type_id=OSTypeId[os_type])
        device = Device(
            type_id=DeviceTypeId.DESKTOP,
            type=DeviceTypeStr.DESKTOP,
            uid=asset["id"],
            os=os_obj,
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
            metadata=metadata,
            device=device,
        )

    def __fetch_devices(self, from_date: str | None) -> Generator[list[dict[str, Any]], None, None]:
        self.log(f"Start fetching devices from Harfanglab API from date {from_date}", level="info")

        devices_url = urljoin(self.base_url, self.AGENT_ENDPOINT)

        params: dict[str, Union[str, int]] = {
            "ordering": self.DEVICE_ORDERING_FIELD,
            "limit": self.limit,
        }

        if from_date:
            params["firstseen"] = from_date

        device_response = self.client.get(devices_url, params=params)
        device_response.raise_for_status()

        while self.running:
            devices = device_response.json()

            self.log(f"Fetched {devices.get('count', 0)} device assets from Harfanglab API", level="info")
            # Check if there are no devices or if the count is zero
            # This is to handle the case where there are no devices returned
            if not devices or devices.get("count") == 0:
                return

            yield devices.get("results", [])

            if next_page := devices.get("next"):
                self.log(f"Fetching next page of devices: {next_page}", level="debug")
                next_page_url = urljoin(self.base_url, next_page)
            else:
                return

            device_response = self.client.get(next_page_url)
            device_response.raise_for_status()

    def next_list_devices(self) -> Generator[list[dict[str, Any]], None, None]:
        orig_date: datetime | None = isoparse(self.most_recent_date_seen) if self.most_recent_date_seen else None
        max_date: datetime | None = None

        self.log("Start looping through devices from Harfanglab API", level="info")
        for devices in self.__fetch_devices(from_date=self.most_recent_date_seen):
            if not devices:
                continue

            last_event = max(devices, key=self.extract_timestamp)
            last_ts = self.extract_timestamp(last_event)

            candidate = last_ts + timedelta(microseconds=1)

            if max_date is None or candidate > max_date:
                max_date = candidate

            yield devices

        if max_date and (orig_date is None or max_date > orig_date):
            self.log(
                f"Finished fetching devices from Harfanglab API and found a new most recent date: {max_date.isoformat()}",
                level="info",
            )
            with self.context as cache:
                cache["most_recent_date_seen"] = max_date.isoformat()

    def get_assets(self) -> Generator[DeviceOCSFModel, None, None]:
        self.log("Start the getting assets generator !!", level="info")
        for devices in self.next_list_devices():
            for device in devices:
                mapped_device: DeviceOCSFModel = self.map_fields(device)
                yield mapped_device
