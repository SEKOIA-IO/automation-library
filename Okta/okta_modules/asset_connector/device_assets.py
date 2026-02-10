"""Okta Device Asset Connector module.

This module provides functionality to collect device assets from Okta
and format them according to OCSF standards.
"""

import asyncio
from collections.abc import AsyncGenerator
from functools import cached_property
from typing import Any, List, Optional
from urllib.parse import urlencode

from dateutil.parser import isoparse
from okta.client import Client as OktaClient
from pydantic import BaseModel, Field
from sekoia_automation.asset_connector import AsyncAssetConnector
from sekoia_automation.asset_connector.models.ocsf.base import Metadata, Product
from sekoia_automation.asset_connector.models.ocsf.device import (
    Device,
    DeviceDataObject,
    DeviceEnrichmentObject,
    DeviceOCSFModel,
    DeviceTypeId,
    DeviceTypeStr,
    EncryptionObject,
    OperatingSystem,
    OSTypeId,
    OSTypeStr,
)
from sekoia_automation.storage import PersistentJSON

from okta_modules import OktaModule


class OktaDeviceProfile(BaseModel):
    """Okta Device Profile."""

    displayName: str
    platform: str
    registered: bool
    secureHardwarePresent: bool
    osVersion: str
    serialNumber: Optional[str] = None
    sid: Optional[str] = None
    diskEncryptionType: Optional[str] = None
    manufacturer: Optional[str] = None
    model: Optional[str] = None


class OktaDevice(BaseModel):
    """Okta Device."""

    id: str
    status: str
    created: str
    lastUpdated: str
    profile: OktaDeviceProfile


class OktaDeviceAssetConnector(AsyncAssetConnector):
    """Asset connector for collecting device data from Okta.

    This connector fetches device information from Okta and formats it
    according to OCSF (Open Cybersecurity Schema Framework) standards.
    """

    module: OktaModule

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the Okta Device Asset Connector.

        Args:
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.
        """
        super().__init__(*args, **kwargs)
        self.context = PersistentJSON("context.json", self._data_path)
        self.new_most_recent_date: Optional[str] = None

    @cached_property
    def client(self) -> OktaClient:
        """Get the Okta client instance.

        Returns:
            Configured OktaClient instance.
        """
        config = {
            "orgUrl": self.module.configuration.base_url,
            "token": self.module.configuration.apikey,
        }
        return OktaClient(config)

    @property
    def most_recent_date_seen(self) -> str | None:
        """Get the most recent date seen from the context cache.

        Returns:
            The most recent date seen as a string, or None if not set.
        """
        with self.context as cache:
            result: str | None = cache.get("most_recent_date_seen", None)

        return result

    def update_checkpoint(self) -> None:
        """Update the checkpoint with the most recent date seen.

        Raises:
            ValueError: If new_most_recent_date is None.
        """
        if self.new_most_recent_date is None:
            self.log("Warning: new_most_recent_date is None, skipping checkpoint update", level="warning")
            return

        try:
            with self.context as cache:
                cache["most_recent_date_seen"] = self.new_most_recent_date
                self.log(f"Checkpoint updated with date: {self.new_most_recent_date}", level="info")
        except Exception as e:
            self.log(f"Failed to update checkpoint: {str(e)}", level="error")

    async def fetch_next_devices(self, url: str) -> tuple[List[OktaDevice], Any]:
        """Fetch devices from the specified URL.

        Args:
            url: The URL to fetch devices from.

        Returns:
            Tuple of (devices list, response object) or ([], None) on error.
        """
        all_devices = []
        try:
            query_params = {}
            if self.most_recent_date_seen:
                query_params = {
                    "search": f'created gt "{self.most_recent_date_seen}"',
                    "sortBy": "created",
                    "sortOrder": "asc",
                }
            if query_params:
                encoded_query_params = urlencode(query_params)
                url += f"/?{encoded_query_params}"

            request, error = await self.client.get_request_executor().create_request(
                method="GET", url=url, body={}, headers={}, oauth=False
            )
            response, error = await self.client.get_request_executor().execute(request, list[OktaDevice])

            if error:
                self.log(f"Error while fetching devices from {url}: {error}", level="error")
                return [], None

            if not response or not response.get_body():
                self.log(f"No devices found at {url}", level="warning")
                return [], None

            # Use list comprehension for better performance
            all_devices = [OktaDevice(**device) for device in response.get_body()]

            return all_devices, response
        except Exception as e:
            self.log(f"Exception while fetching devices from {url}: {e}", level="error")
            return [], None

    async def next_list_devices(self) -> AsyncGenerator[OktaDevice, None]:
        """Fetch all devices from Okta.

        Yields:
            Device objects from Okta.
        """
        devices, response = await self.fetch_next_devices("/api/v1/devices")
        for device in devices:
            yield device
            self.new_most_recent_date = device.created

        while response and response.has_next():
            devices, response = await self.fetch_next_devices(response._next)
            for device in devices:
                yield device
                self.new_most_recent_date = device.created

    def get_device_os(self, platform: str, version: str) -> OperatingSystem:
        """Get operating system information for a device.

        Args:
            platform: The device platform (windows, macos, linux, ios, android).
            version: The operating system version.

        Returns:
            OperatingSystem object with mapped OS information.
        """
        # Handle None or empty version
        version = version or "Unknown"

        match platform.lower() if platform else "":
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
                return OperatingSystem(
                    name=platform if platform is not None else "Unknown",
                    version=version,
                    type=OSTypeStr.OTHER,
                    type_id=OSTypeId.OTHER,
                )

    async def map_fields(self, okta_device: OktaDevice) -> DeviceOCSFModel:
        """Map Okta device data to OCSF format.

        Args:
            okta_device: OktaDevice object containing device data.

        Returns:
            DeviceOCSFModel instance with mapped device data.

        Raises:
            ValueError: If required device data is missing.
        """
        # Validate required fields
        if not okta_device.id:
            raise ValueError("Device ID is required")
        if not okta_device.profile or not okta_device.profile.displayName:
            raise ValueError("Device profile and displayName are required")

        # Parse timestamps
        created_timestamp = isoparse(okta_device.created).timestamp()
        last_updated_timestamp = isoparse(okta_device.lastUpdated).timestamp()

        # Determine management and compliance status
        is_managed = okta_device.profile.registered
        is_compliant = okta_device.status == "ACTIVE" and okta_device.profile.registered

        device = Device(
            hostname=okta_device.profile.displayName,
            uid=okta_device.id,
            type_id=DeviceTypeId.OTHER,
            type=DeviceTypeStr.OTHER,
            location=None,
            os=self.get_device_os(okta_device.profile.platform, okta_device.profile.osVersion),
            vendor_name=okta_device.profile.manufacturer,
            model=okta_device.profile.model,
            created_time=created_timestamp,
            last_seen_time=last_updated_timestamp,
            is_managed=is_managed,
            is_compliant=is_compliant,
        )

        # Build enrichment data
        enrichments = []

        # Collect device data for enrichment
        device_data_dict = {}

        # Add disk encryption if available
        if okta_device.profile.diskEncryptionType:
            # Map disk encryption type to partitions
            partitions = {}
            if okta_device.profile.diskEncryptionType == "ALL_INTERNAL_VOLUMES":
                partitions["all_internal"] = "Enabled"
            elif okta_device.profile.diskEncryptionType == "USER":
                partitions["user"] = "Enabled"
            elif okta_device.profile.diskEncryptionType == "FULL":
                partitions["full"] = "Enabled"
            else:
                partitions["none"] = "Disabled"

            device_data_dict["Storage_encryption"] = EncryptionObject(partitions=partitions)

        # Add hardware identifiers as user list (using available field)
        hardware_info = []
        if okta_device.profile.serialNumber:
            hardware_info.append(f"serial_number:{okta_device.profile.serialNumber}")
        if okta_device.profile.sid:
            hardware_info.append(f"windows_sid:{okta_device.profile.sid}")
        if okta_device.profile.secureHardwarePresent is not None:
            hardware_info.append(f"secure_hardware_present:{okta_device.profile.secureHardwarePresent}")

        if hardware_info:
            device_data_dict["Users"] = hardware_info

        # Create enrichment if we have any data
        if device_data_dict:
            device_data = DeviceDataObject(**device_data_dict)
            enrichment = DeviceEnrichmentObject(name="device_info", value="hardware_and_security", data=device_data)
            enrichments.append(enrichment)

        return DeviceOCSFModel(
            activity_id=2,
            activity_name="Collect",
            category_name="Discovery",
            category_uid=5,
            class_name="Device Inventory Info",
            class_uid=5001,
            device=device,
            time=created_timestamp,
            metadata=Metadata(product=Product(name="Okta", vendor_name="Okta", version="N/A"), version="1.6.0"),
            severity="Informational",
            severity_id=1,
            type_name="Device Inventory Info: Collect",
            type_uid=500102,
            enrichments=enrichments if enrichments else None,
        )

    async def get_assets(self) -> AsyncGenerator[DeviceOCSFModel, None]:
        """Generate device assets from Okta.

        Yields:
            DeviceOCSFModel instances for each device found in Okta.
        """
        self.log("Starting Okta device assets generator", level="info")
        self.log(f"Data path: {self._data_path.absolute()}", level="info")

        async for device in self.next_list_devices():
            try:
                yield await self.map_fields(device)
            except Exception as e:
                device_id = getattr(device, "id", "unknown")
                self.log(f"Error while mapping device {device_id}: {e}", level="error")
                continue
