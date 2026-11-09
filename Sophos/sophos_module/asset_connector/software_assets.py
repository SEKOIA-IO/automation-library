from __future__ import annotations

from collections.abc import Generator
from datetime import datetime, timezone
from functools import cached_property
from typing import Any

from dateutil.parser import isoparse
from sekoia_automation.asset_connector import AssetConnector
from sekoia_automation.asset_connector.models.ocsf.base import Metadata, Product
from sekoia_automation.asset_connector.models.ocsf.device import (
    Device,
    DeviceTypeId,
    DeviceTypeStr,
    OperatingSystem,
    OSTypeId,
    OSTypeStr,
)
from sekoia_automation.asset_connector.models.ocsf.software import (
    PackageTypeId,
    PackageTypeStr,
    SoftwareBillOfMaterials,
    SoftwareEnrichmentObject,
    SoftwareOCSFModel,
    SoftwarePackage,
)
from sekoia_automation.storage import PersistentJSON

from sophos_module.asset_connector.model import (
    SophosEndpoint,
    SophosEndpointsResponse,
    SophosModule_,
)
from sophos_module.client import SophosApiClient
from sophos_module.client.auth import SophosApiAuthentication

SOPHOS_VENDOR_NAME = "Sophos"


class SophosSoftwareAssetConnector(AssetConnector):
    """
    Asset connector for Sophos installed software modules.

    Uses GET /endpoint/v1/endpoints and extracts the ``modules`` array from each
    endpoint.  Each module represents a Sophos software component
    (e.g. coreAgent, interceptX, deviceEncryption) installed on the endpoint and
    is mapped to an OCSF SoftwareOCSFModel paired with its parent Device.

    No extra API call is needed — all data is already available in the standard
    endpoint list response.
    """

    PRODUCT_NAME: str = "Sophos EDR"
    PRODUCT_VERSION: str = "N/A"
    OCSF_VERSION: str = "1.6.0"
    PAGE_SIZE: int = 500

    # OCSF Constants — Software Inventory Info: Collect
    ACTIVITY_ID: int = 2
    ACTIVITY_NAME: str = "Collect"
    CATEGORY_NAME: str = "Discovery"
    CATEGORY_UID: int = 5
    CLASS_NAME: str = "Software Inventory Info"
    CLASS_UID: int = 5002
    TYPE_NAME: str = "Software Inventory Info: Collect"
    TYPE_UID: int = 500202

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.context = PersistentJSON("software_context.json", self._data_path)

    @cached_property
    def client(self) -> SophosApiClient:
        cfg = self.module.configuration
        auth = SophosApiAuthentication(
            api_host=cfg.api_host,
            authorization_url=cfg.oauth2_authorization_url,
            client_id=cfg.client_id,
            client_secret=cfg.client_secret,
        )
        return SophosApiClient(auth=auth)

    @cached_property
    def metadata(self) -> Metadata:
        return Metadata(
            product=Product(name=self.PRODUCT_NAME, version=self.PRODUCT_VERSION),
            version=self.OCSF_VERSION,
        )

    @staticmethod
    def _parse_ts(ts: str | None) -> float | None:
        if not ts:
            return None
        try:
            return isoparse(ts).timestamp()
        except (ValueError, AttributeError):
            return None

    @staticmethod
    def _get_os(endpoint: SophosEndpoint) -> OperatingSystem:
        os_data = endpoint.os
        platform: str = (os_data.platform or "").lower() if os_data else ""
        os_name: str | None = os_data.name if os_data else None
        _mapping: dict[str, tuple[OSTypeId, OSTypeStr]] = {
            "windows": (OSTypeId.WINDOWS, OSTypeStr.WINDOWS),
            "linux": (OSTypeId.LINUX, OSTypeStr.LINUX),
            "macos": (OSTypeId.MACOS, OSTypeStr.MACOS),
            "android": (OSTypeId.ANDROID, OSTypeStr.ANDROID),
        }
        type_id, type_str = _mapping.get(platform, (OSTypeId.UNKNOWN, OSTypeStr.UNKNOWN))
        return OperatingSystem(name=os_name, type=type_str, type_id=type_id)

    @staticmethod
    def _get_device_type(endpoint: SophosEndpoint) -> tuple[DeviceTypeId, DeviceTypeStr]:
        ep_type: str = (endpoint.type or "").lower()
        if ep_type == "server":
            return DeviceTypeId.SERVER, DeviceTypeStr.SERVER
        if ep_type == "computer":
            return DeviceTypeId.DESKTOP, DeviceTypeStr.DESKTOP
        return DeviceTypeId.UNKNOWN, DeviceTypeStr.UNKNOWN

    def _build_device(self, endpoint: SophosEndpoint) -> Device:
        type_id, type_str = self._get_device_type(endpoint)
        os = self._get_os(endpoint)
        primary_ip: str | None = (
            endpoint.ipv4Addresses[0]
            if endpoint.ipv4Addresses
            else (endpoint.ipv6Addresses[0] if endpoint.ipv6Addresses else None)
        )
        return Device(
            uid=endpoint.id,
            hostname=endpoint.hostname,
            name=endpoint.hostname,
            type_id=type_id,
            type=type_str,
            os=os,
            ip=primary_ip,
            is_managed=True,
        )

    def map_software_fields(
        self,
        endpoint: SophosEndpoint,
        module: SophosModule_,
    ) -> SoftwareOCSFModel | None:
        """
        Map a Sophos endpoint module to an OCSF SoftwareOCSFModel.
        Returns None when mandatory fields are missing.
        """
        if not endpoint.id:
            self.log(f"Skipping module: parent endpoint has no 'id'. Module: {module}", level="warning")
            return None
        if not endpoint.hostname:
            self.log(f"Skipping module on endpoint {endpoint.id}: missing 'hostname'", level="warning")
            return None
        if not module.name:
            self.log(f"Skipping unnamed module on endpoint {endpoint.id}", level="warning")
            return None

        device = self._build_device(endpoint)

        software = SoftwareEnrichmentObject(
            name=module.name,
            version=module.version,
            vendor_name=SOPHOS_VENDOR_NAME,
        )

        # Build SBOM only when version is available (SoftwarePackage.version is required)
        sbom: SoftwareBillOfMaterials | None = None
        if module.version:
            package = SoftwarePackage(
                name=module.name,
                version=module.version,
                type=PackageTypeStr.APPLICATION,
                type_id=PackageTypeId.APPLICATION,
            )
            sbom = SoftwareBillOfMaterials(package=package)

        # Use lastSeenAt as proxy event time, fallback to now
        event_time = self._parse_ts(endpoint.lastSeenAt) or datetime.now(tz=timezone.utc).timestamp()

        return SoftwareOCSFModel(
            activity_id=self.ACTIVITY_ID,
            activity_name=self.ACTIVITY_NAME,
            category_name=self.CATEGORY_NAME,
            category_uid=self.CATEGORY_UID,
            class_name=self.CLASS_NAME,
            class_uid=self.CLASS_UID,
            type_name=self.TYPE_NAME,
            type_uid=self.TYPE_UID,
            severity="Informational",
            severity_id=1,
            time=event_time,
            metadata=self.metadata,
            device=device,
            software=software,
            sbom=sbom,
        )

    def _iter_endpoints(self) -> Generator[SophosEndpoint, None, None]:
        """Yield every endpoint from the Sophos Central API (all pages)."""
        params: dict[str, Any] = {"pageSize": self.PAGE_SIZE, "view": "full"}

        while self.running:
            response = self.client.list_endpoints(params)
            response.raise_for_status()
            data: SophosEndpointsResponse = SophosEndpointsResponse.model_validate(response.json())

            yield from data.items

            next_key: str | None = data.pages.nextKey if data.pages else None
            if not next_key:
                break
            params["pageFromKey"] = next_key

    def update_checkpoint(self) -> None:
        """No cursor-based checkpoint for software assets — full sync every run."""
        self.log("Software asset collection checkpoint updated", level="debug")

    def get_assets(self) -> Generator[SoftwareOCSFModel, None, None]:
        """
        Main entry point.

        For each endpoint, iterate over ``endpoint.modules`` and yield one
        SoftwareOCSFModel per installed Sophos module.
        """
        self.log("Starting Sophos software asset collection", level="info")
        total = 0
        skipped = 0

        try:
            for endpoint in self._iter_endpoints():
                if not endpoint.id:
                    skipped += 1
                    continue
                for module in endpoint.modules:
                    mapped = self.map_software_fields(endpoint, module)
                    if mapped is not None:
                        total += 1
                        yield mapped
                    else:
                        skipped += 1
        except Exception as exc:
            self.log(
                f"Software asset collection failed – collected={total}, skipped={skipped}, error={exc}",
                level="error",
            )
            raise

        self.log(f"Sophos software asset collection complete – total={total}, skipped={skipped}", level="info")
