from collections.abc import Generator
from datetime import datetime, timezone
from functools import cached_property
from typing import Any

from dateutil.parser import isoparse
from sekoia_automation.asset_connector import AssetConnector
from sekoia_automation.asset_connector.models.ocsf.base import Metadata, Product
from sekoia_automation.asset_connector.models.ocsf.device import (
    Device,
    DeviceDataObject,
    DeviceEnrichmentObject,
    DeviceOCSFModel,
    DeviceTypeId,
    DeviceTypeStr,
    NetworkInterface,
    OperatingSystem,
    OSTypeId,
    OSTypeStr,
)
from sekoia_automation.asset_connector.models.ocsf.organization import Organization
from sekoia_automation.asset_connector.models.ocsf.group import Group
from sekoia_automation.storage import PersistentJSON

from sophos_module.client import SophosApiClient
from sophos_module.client.auth import SophosApiAuthentication


class SophosDeviceAssetConnector(AssetConnector):
    """
    Asset connector for Sophos EDR devices.
    Collects endpoint devices from the Sophos Central API
    """

    PRODUCT_NAME: str = "Sophos EDR"
    PRODUCT_VERSION: str = "N/A"
    OCSF_VERSION: str = "1.6.0"
    PAGE_SIZE: int = 500

    # OCSF Constants
    ACTIVITY_ID: int = 2
    ACTIVITY_NAME: str = "Collect"
    CATEGORY_NAME: str = "Discovery"
    CATEGORY_UID: int = 5
    CLASS_NAME: str = "Device Inventory Info"
    CLASS_UID: int = 5001
    TYPE_NAME: str = "Device Inventory Info: Collect"
    TYPE_UID: int = 500102

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.context = PersistentJSON("context.json", self._data_path)
        self._latest_time: str | None = None

    @property
    def last_seen_cursor(self) -> str | None:
        with self.context as cache:
            return cache.get("last_seen_cursor")

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
    def _normalize_mac(mac: str | None) -> str | None:
        if not mac:
            return None
        return mac.replace("-", ":").upper()

    def _get_os(self, endpoint: dict[str, Any]) -> OperatingSystem:
        """Map Sophos os object to OCSF OperatingSystem."""
        os_data: dict[str, Any] = endpoint.get("os") or {}
        platform: str = (os_data.get("platform") or "").lower()
        os_name: str | None = os_data.get("name")

        _mapping: dict[str, tuple[OSTypeId, OSTypeStr]] = {
            "windows": (OSTypeId.WINDOWS, OSTypeStr.WINDOWS),
            "linux": (OSTypeId.LINUX, OSTypeStr.LINUX),
            "macos": (OSTypeId.MACOS, OSTypeStr.MACOS),
            "android": (OSTypeId.ANDROID, OSTypeStr.ANDROID),
        }

        type_id, type_str = _mapping.get(platform, (OSTypeId.UNKNOWN, OSTypeStr.UNKNOWN))
        return OperatingSystem(name=os_name, type=type_str, type_id=type_id)

    @staticmethod
    def _get_device_type(endpoint: dict[str, Any]) -> tuple[DeviceTypeId, DeviceTypeStr]:
        """Map Sophos endpoint type (computer / server) to OCSF device type."""
        ep_type: str = (endpoint.get("type") or "").lower()
        if ep_type == "server":
            return DeviceTypeId.SERVER, DeviceTypeStr.SERVER
        if ep_type == "computer":
            return DeviceTypeId.DESKTOP, DeviceTypeStr.DESKTOP
        return DeviceTypeId.UNKNOWN, DeviceTypeStr.UNKNOWN

    @staticmethod
    def _get_network_interfaces(endpoint: dict[str, Any]) -> list[NetworkInterface] | None:
        """Build NetworkInterface list from ipv4, ipv6 and mac addresses."""
        ipv4_list: list[str] = endpoint.get("ipv4Addresses") or []
        ipv6_list: list[str] = endpoint.get("ipv6Addresses") or []
        mac_list: list[str] = endpoint.get("macAddresses") or []
        hostname: str | None = endpoint.get("hostname")

        interfaces: list[NetworkInterface] = []

        # One interface per IPv4, attach matching MAC if available
        for idx, ip in enumerate(ipv4_list):
            mac = mac_list[idx] if idx < len(mac_list) else None
            interfaces.append(
                NetworkInterface(
                    hostname=hostname if idx == 0 else None,
                    ip=ip,
                    mac=SophosDeviceAssetConnector._normalize_mac(mac),
                    name=f"eth{idx}",
                )
            )

        # Additional IPv6-only entries
        for idx, ip6 in enumerate(ipv6_list):
            mac_idx = len(ipv4_list) + idx
            mac = mac_list[mac_idx] if mac_idx < len(mac_list) else None
            interfaces.append(
                NetworkInterface(
                    ip=ip6,
                    mac=SophosDeviceAssetConnector._normalize_mac(mac),
                    name=f"eth{mac_idx}",
                )
            )

        return interfaces if interfaces else None

    @staticmethod
    def _is_compliant(endpoint: dict[str, Any]) -> bool | None:
        """
        Determine compliance based on Sophos health.overall field:
          good  → True
          bad   → False
          other → None (unknown)
        """
        health: dict[str, Any] = endpoint.get("health") or {}
        overall: str = (health.get("overall") or "").lower()
        if overall == "good":
            return True
        if overall in ("bad", "suspicious"):
            return False
        return None

    @staticmethod
    def _get_firewall_status(endpoint: dict[str, Any]) -> str | None:
        """
        Sophos does not expose a direct firewall field.
        We infer from tamperProtectionEnabled as a proxy.
        """
        if endpoint.get("tamperProtectionEnabled") is True:
            return "Enabled"
        if endpoint.get("tamperProtectionEnabled") is False:
            return "Disabled"
        return None

    @staticmethod
    def _get_organization(endpoint: dict[str, Any]) -> Organization | None:
        tenant: dict[str, Any] = endpoint.get("tenant") or {}
        tenant_id: str | None = tenant.get("id")
        if tenant_id:
            return Organization(uid=tenant_id, name=tenant_id)
        return None

    def _get_enrichments(self, endpoint: dict[str, Any]) -> list[DeviceEnrichmentObject] | None:
        """Build enrichment objects from Sophos-specific fields."""
        firewall_status = self._get_firewall_status(endpoint)

        device_data = DeviceDataObject(
            Firewall_status=firewall_status,  # type: ignore[arg-type]
        )

        return [
            DeviceEnrichmentObject(
                name="compliance",
                value="hygiene",
                data=device_data,
            )
        ]

    def _get_groups(self, endpoint: dict[str, Any]) -> list[Group] | None:
        """Get Groups from Sophos"""
        sophos_groups = endpoint.get("group")
        if not sophos_groups:
            return None

        return [
            Group(
                uid=group.get("id"),
                name=group["name"],
            )
            for group in sophos_groups
            if group.get("name")
        ] or None

    @staticmethod
    def _is_trusted(endpoint: dict[str, Any]) -> bool | None:
        health: dict[str, Any] = endpoint.get("health") or {}
        overall: str = (health.get("overall") or "").lower()
        isolation: dict[str, Any] = endpoint.get("isolation") or {}
        isolation_status: str = (isolation.get("status") or "").lower()
        tamper_enabled: bool | None = endpoint.get("tamperProtectionEnabled")

        if isolation_status == "isolated":
            return False

        if overall == "good" and tamper_enabled is True:
            return True

        if overall in ("bad", "suspicious"):
            return False

        return None

    def map_device_fields(self, endpoint: dict[str, Any]) -> DeviceOCSFModel | None:
        """
        Map a Sophos endpoint JSON record to an OCSF DeviceOCSFModel.
        Returns None if mandatory fields are missing.
        """
        uid: str | None = endpoint.get("id")
        hostname: str | None = endpoint.get("hostname")

        if not uid:
            self.log(f"Skipping endpoint: missing 'id'. Data: {endpoint}", level="warning")
            return None
        if not hostname:
            self.log(f"Skipping endpoint {uid}: missing 'hostname'", level="warning")
            return None

        type_id, type_str = self._get_device_type(endpoint)
        os = self._get_os(endpoint)
        interfaces = self._get_network_interfaces(endpoint)
        org = self._get_organization(endpoint)
        enrichments = self._get_enrichments(endpoint)
        is_compliant = self._is_compliant(endpoint)
        groups = self._get_groups(endpoint)

        # Use first IPv4 as primary IP otherwise IPv6
        ipv4_list: list[str] = endpoint.get("ipv4Addresses") or []
        ipv6_list: list[str] = endpoint.get("ipv6Addresses") or []
        primary_ip: str | None = ipv4_list[0] if ipv4_list else (ipv6_list[0] if ipv6_list else None)

        # Cloud region
        cloud: dict[str, Any] = endpoint.get("cloud") or {}
        region: str | None = cloud.get("provider")

        # Associated person (user)
        associated_person: dict[str, Any] = endpoint.get("associatedPerson") or {}
        person_name: str | None = associated_person.get("name") or None

        # Timestamps
        last_seen_ts = self._parse_ts(endpoint.get("lastSeenAt"))
        registered_ts = self._parse_ts(endpoint.get("registeredAt"))

        # Event time: prefer lastSeenAt, fallback to registeredAt, then now
        event_time = last_seen_ts or registered_ts or datetime.now(tz=timezone.utc).timestamp()

        device = Device(
            type_id=type_id,
            type=type_str,
            uid=uid,
            os=os,
            hostname=hostname,
            created_time=registered_ts,
            first_seen_time=registered_ts,
            desc=person_name,
            groups=groups,
            is_compliant=is_compliant,
            name=hostname,
            ip=primary_ip,
            network_interfaces=interfaces,
            org=org,
            region=region,
            is_managed=True,
            is_trusted=self._is_trusted(endpoint),
            last_seen_time=last_seen_ts,
        )

        return DeviceOCSFModel(
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
            enrichments=enrichments,
        )

    def _iter_endpoints(self) -> Generator[dict[str, Any], None, None]:
        params: dict[str, Any] = {
            "pageSize": self.PAGE_SIZE,
            "view": "full",
        }

        if self.last_seen_cursor:
            params["lastSeenAfter"] = self.last_seen_cursor

        while self.running:
            response = self.client.list_endpoints(params)
            response.raise_for_status()
            data = response.json()

            items: list[dict[str, Any]] = data.get("items") or []
            for item in items:
                last_seen = item.get("lastSeenAt")
                if last_seen:
                    if self._latest_time is None or last_seen > self._latest_time:
                        self._latest_time = last_seen
                yield item

            pages = data.get("pages") or {}
            next_key: str | None = pages.get("nextKey")
            if not next_key:
                break
            params["pageFromKey"] = next_key

    def update_checkpoint(self) -> None:
        if self._latest_time:
            with self.context as cache:
                cache["last_seen_cursor"] = self._latest_time
            self.log(f"Checkpoint updated successfully - New timestamp: {self._latest_time}", level="debug")
        else:
            self.log("No checkpoint update needed - No new timestamp available", level="debug")

    def get_assets(self) -> Generator[DeviceOCSFModel, None, None]:
        """Main entry point: yield all Sophos device assets as OCSF models."""
        self.log("Starting Sophos device asset collection", level="info")
        total = 0
        skipped = 0

        try:
            for endpoint in self._iter_endpoints():
                mapped = self.map_device_fields(endpoint)
                if mapped is not None:
                    total += 1
                    yield mapped
                else:
                    skipped += 1
        except Exception as exc:
            self.log(f"Asset collection failed – collected={total}, skipped={skipped}, error={exc}", level="error")
            raise

        self.log(f"Sophos device asset collection complete – total={total}, skipped={skipped}", level="info")
