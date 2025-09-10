import asyncio
from functools import cached_property
from typing import Any, List
from dateutil.parser import isoparse
from collections.abc import Generator
from sekoia_automation.asset_connector import AssetConnector
from sekoia_automation.asset_connector.models.ocsf.base import (
    Metadata,
    Product,
)
from sekoia_automation.asset_connector.models.ocsf.device import (
    DeviceOCSFModel,
    Device,
    DeviceTypeId,
    DeviceTypeStr,
    OperatingSystem,
    OSTypeId,
    OSTypeStr,
)
from sekoia_automation.storage import PersistentJSON

from okta.client import Client as OktaClient
from pydantic import BaseModel
from urllib.parse import urlencode


class OktaDeviceProfile(BaseModel):
    """Okta Device Profile."""

    displayName: str
    platform: str
    serialNumber: str
    sid: str
    registered: bool
    secureHardwarePresent: bool
    diskEncryptionType: str
    osVersion: str


class OktaDevice(BaseModel):
    """Okta Device."""

    id: str
    status: str
    created: str
    lastUpdated: str
    profile: OktaDeviceProfile


class OktaDeviceAssetConnector(AssetConnector):
    """Okta Device Asset Connector."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.context = PersistentJSON("context.json", self._data_path)

    @cached_property
    def client(self):
        config = {"orgUrl": self.module.configuration["base_url"], "token": self.module.configuration["apikey"]}
        return OktaClient(config)

    async def fetch_next_devices(self, url: str) -> tuple[List[OktaDevice], Any]:
        try:
            request, error = await self.client.get_request_executor().create_request(
                method="GET", url=url, body={}, headers={}, oauth=False
            )
            response, error = await self.client.get_request_executor().execute(request, list[OktaDevice])
            if error:
                self.log(f"Error while fetching devices from {url}: {error}", level="error")
                return []
            devices: list[OktaDevice] = response.get_type()(response.get_body())
            if not devices:
                self.log(f"No devices found at {url}", level="warning")
                return []
            return devices, response
        except Exception as e:
            self.log(f"Exception while fetching devices from {url}: {e}", level="error")
            return [], None

    async def next_list_devices(self) -> list[OktaDevice]:
        all_devices = []
        devices, response = await self.fetch_next_devices("/api/v1/devices")
        all_devices.extend(devices)
        while response.has_next():
            devices, response = await self.fetch_next_devices(response._next)
            all_devices.extend(devices)
        return all_devices

    def get_device_os(self, platform: str, version: str) -> OperatingSystem:
        match platform.lower():
            case "windows":
                return OperatingSystem(
                    name="Windows", version=version, type=OSTypeStr.WINDOWS, type_id=OSTypeId.WINDOWS
                )
            case "macos":
                return OperatingSystem(name="macOS", version=version, type=OSTypeStr.MACOS, type_id=OSTypeId.MACOS)
            case "linux":
                return OperatingSystem(name="Linux", version=version, type=OSTypeStr.LINUX, type_id=OSTypeId.LINUX)
            case "ios":
                return OperatingSystem(name="iOS", version=version, type=OSTypeStr.IOS, type_id=OSTypeId.IOS)
            case "android":
                return OperatingSystem(
                    name="Android", version=version, type=OSTypeStr.ANDROID, type_id=OSTypeId.ANDROID
                )
            case _:
                return OperatingSystem(name=platform, version=version, type=OSTypeStr.OTHER, type_id=OSTypeId.OTHER)

    async def map_fields(self, okta_device: OktaDevice) -> DeviceOCSFModel:
        device = Device(
            hostname=okta_device.get("profile").get("displayName"),
            uid=okta_device.get("id"),
            type_id=DeviceTypeId.OTHER,
            type=DeviceTypeStr.OTHER,
            location=None,
            os=self.get_device_os(
                okta_device.get("profile").get("platform"), okta_device.get("profile").get("osVersion")
            ),
        )
        return DeviceOCSFModel(
            activity_id=2,
            activity_name="Collect",
            category_name="Discovery",
            category_uid=5,
            class_name="Device Inventory Info",
            class_uid=5001,
            device=device,
            time=isoparse(okta_device.get("created")).timestamp(),
            metadata=Metadata(product=Product(name="Okta", vendor_name="Okta", version="N/A"), version="1.6.0"),
            severity="Informational",
            severity_id=1,
            type_name="Software Inventory Info: Collect",
            type_uid=500102,
        )

    def get_assets(self) -> Generator[DeviceOCSFModel, None, None]:
        self.log("Start the getting okta device assets generator !", level="info")
        self.log(f"The data path is: {self._data_path.absolute()}", level="info")
        loop = asyncio.get_event_loop()
        for device in loop.run_until_complete(self.next_list_devices()):
            try:
                yield loop.run_until_complete(self.map_fields(device))
            except Exception as e:
                self.log(f"Error while mapping device {device.get('id')}: {e}", level="error")
                continue
