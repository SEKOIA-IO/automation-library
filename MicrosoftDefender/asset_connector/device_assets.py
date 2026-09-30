from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from functools import cached_property
from urllib.parse import urlencode, urljoin

from azure.identity.aio import ClientSecretCredential
from dateutil.parser import isoparse
from kiota_abstractions.base_request_configuration import RequestConfiguration
from msgraph import GraphServiceClient
from msgraph.generated.device_management.managed_devices.managed_devices_request_builder import (
    ManagedDevicesRequestBuilder,
)
from msgraph.generated.models.managed_device import ManagedDevice
from sekoia_automation.asset_connector import AsyncAssetConnector
from sekoia_automation.asset_connector.models.ocsf.base import Metadata, Product
from sekoia_automation.asset_connector.models.ocsf.device import (
    Device,
    DeviceEnrichmentObject,
    DeviceOCSFModel,
    DeviceTypeId,
    DeviceTypeStr,
    Group,
    NetworkInterface,
    NetworkInterfaceTypeId,
    NetworkInterfaceTypeStr,
    OperatingSystem,
    OSTypeId,
    OSTypeStr,
)
from sekoia_automation.asset_connector.models.ocsf.risk_level import RiskLevelId, RiskLevelStr
from sekoia_automation.storage import PersistentJSON

from asset_connector.models import DefenderMachine, DefenderMachineListResponse
from microsoftdefender_modules import MicrosoftDefenderModule
from microsoftdefender_modules.client import ApiClient
from microsoftdefender_modules.logging import get_logger

logger = get_logger(__name__)

# Mapping from Defender osPlatform string to OCSF OS type
OS_TYPE_MAP: dict[str, tuple[OSTypeStr, OSTypeId]] = {
    "windows": (OSTypeStr.WINDOWS, OSTypeId.WINDOWS),
    "linux": (OSTypeStr.LINUX, OSTypeId.LINUX),
    "macos": (OSTypeStr.MACOS, OSTypeId.MACOS),
    "android": (OSTypeStr.ANDROID, OSTypeId.ANDROID),
    "ios": (OSTypeStr.IOS, OSTypeId.IOS),
    "ipados": (OSTypeStr.IPADOS, OSTypeId.IPADOS),
}

# Mapping from Defender riskScore to OCSF risk level
RISK_LEVEL_MAP: dict[str, tuple[RiskLevelStr, RiskLevelId]] = {
    "informational": (RiskLevelStr.INFO, RiskLevelId.INFO),
    "low": (RiskLevelStr.LOW, RiskLevelId.LOW),
    "medium": (RiskLevelStr.MEDIUM, RiskLevelId.MEDIUM),
    "high": (RiskLevelStr.HIGH, RiskLevelId.HIGH),
    "critical": (RiskLevelStr.CRITICAL, RiskLevelId.CRITICAL),
}

GRAPH_SCOPES: list[str] = ["https://graph.microsoft.com/.default"]

# Mapping from Defender interface type string to OCSF network interface type
NETWORK_INTERFACE_TYPE_MAP: dict[str, tuple[NetworkInterfaceTypeStr, NetworkInterfaceTypeId]] = {
    "ethernet": (NetworkInterfaceTypeStr.WIRED, NetworkInterfaceTypeId.WIRED),
    "wifi": (NetworkInterfaceTypeStr.WIRELESS, NetworkInterfaceTypeId.WIRELESS),
}


class MicrosoftDefenderDeviceAssetConnector(AsyncAssetConnector):
    module: MicrosoftDefenderModule

    # OCSF Constants for Device Inventory Info
    ACTIVITY_ID: int = 2
    ACTIVITY_NAME: str = "Collect"
    CATEGORY_NAME: str = "Discovery"
    CATEGORY_UID: int = 5
    CLASS_NAME: str = "Device Inventory Info"
    CLASS_UID: int = 5001
    TYPE_NAME: str = "Device Inventory Info: Collect"
    TYPE_UID: int = 500102

    PRODUCT_NAME: str = "Microsoft Defender for Endpoint"
    PRODUCT_VERSION: str = "1.0"
    METADATA_VERSION: str = "1.5.0"

    MACHINES_ENDPOINT: str = "/api/machines"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.context = PersistentJSON("device_context.json", self._data_path)
        self._latest_time_raw: str | None = None

    @property
    def most_recent_date_seen(self) -> str | None:
        with self.context as cache:
            return cache.get("most_recent_date_seen")

    @asynccontextmanager
    async def _graph_client(self) -> AsyncGenerator[GraphServiceClient, None]:
        async with ClientSecretCredential(
            tenant_id=self.module.configuration.tenant_id,
            client_id=self.module.configuration.app_id,
            client_secret=self.module.configuration.app_secret,
        ) as credential:
            yield GraphServiceClient(credentials=credential, scopes=GRAPH_SCOPES)

    @cached_property
    def defender_client(self) -> ApiClient:
        return ApiClient(
            base_url=self.module.configuration.base_url,
            app_id=self.module.configuration.app_id,
            app_secret=self.module.configuration.app_secret,
            tenant_id=self.module.configuration.tenant_id,
        )

    @cached_property
    def metadata(self) -> Metadata:
        return Metadata(
            product=Product(name=self.PRODUCT_NAME, version=self.PRODUCT_VERSION),
            version=self.METADATA_VERSION,
        )

    @staticmethod
    def _resolve_os_type(os_platform: str | None) -> tuple[OSTypeStr, OSTypeId]:
        if not os_platform:
            return OSTypeStr.UNKNOWN, OSTypeId.UNKNOWN
        normalized = os_platform.strip().lower()
        for key, value in OS_TYPE_MAP.items():
            if key in normalized:
                return value
        return OSTypeStr.OTHER, OSTypeId.OTHER

    @staticmethod
    def _resolve_device_type(os_str: OSTypeStr) -> tuple[DeviceTypeStr, DeviceTypeId]:
        if os_str in (OSTypeStr.ANDROID, OSTypeStr.IOS, OSTypeStr.IPADOS):
            return DeviceTypeStr.MOBILE, DeviceTypeId.MOBILE
        return DeviceTypeStr.DESKTOP, DeviceTypeId.DESKTOP

    @staticmethod
    def _resolve_risk_level(risk_score: str | None) -> tuple[RiskLevelStr | None, RiskLevelId | None]:
        if not risk_score:
            return None, None
        normalized = risk_score.strip().lower()
        if normalized in RISK_LEVEL_MAP:
            return RISK_LEVEL_MAP[normalized]
        return RiskLevelStr.OTHER, RiskLevelId.OTHER

    def build_device_from_machine(
        self,
        machine: DefenderMachine,
        managed_device: ManagedDevice | None = None,
    ) -> Device:
        os_type_str, os_type_id = self._resolve_os_type(machine.osPlatform)
        device_type_str, device_type_id = self._resolve_device_type(os_type_str)
        risk_level_str, risk_level_id = self._resolve_risk_level(machine.riskScore)

        first_seen_time = None
        last_seen_time = None
        if machine.firstSeen:
            first_seen_time = isoparse(machine.firstSeen).timestamp()
        if machine.lastSeen:
            last_seen_time = isoparse(machine.lastSeen).timestamp()

        # Build OS name from osPlatform + version/osBuild
        os_name = machine.osPlatform or ""
        if machine.osBuild:
            os_name = f"{os_name} (Build {machine.osBuild})"

        # Enrich from managed_device if available
        network_interfaces = None
        imei_list = None
        meid = None
        iccid = None
        udid = None
        is_compliant = None
        is_personal = None
        is_supervised = None
        model = None
        vendor_name = None

        uid_alt = machine.aadDeviceId
        groups: list[Group] | None = None
        if machine.rbacGroupName:
            groups = [
                Group(
                    name=machine.rbacGroupName,
                    uid=str(machine.rbacGroupId) if machine.rbacGroupId is not None else None,
                )
            ]

        if managed_device:
            if managed_device.wi_fi_mac_address or managed_device.ethernet_mac_address:
                interfaces = []
                if managed_device.ethernet_mac_address:
                    interfaces.append(
                        NetworkInterface(
                            mac=managed_device.ethernet_mac_address,
                            name="ethernet",
                            type=NetworkInterfaceTypeStr.WIRED,
                            type_id=NetworkInterfaceTypeId.WIRED,
                        )
                    )
                if managed_device.wi_fi_mac_address:
                    interfaces.append(
                        NetworkInterface(
                            mac=managed_device.wi_fi_mac_address,
                            name="wifi",
                            type=NetworkInterfaceTypeStr.WIRELESS,
                            type_id=NetworkInterfaceTypeId.WIRELESS,
                        )
                    )
                network_interfaces = interfaces

            if managed_device.imei:
                imei_list = [managed_device.imei]
            meid = managed_device.meid
            iccid = managed_device.iccid
            udid = managed_device.udid
            model = managed_device.model
            vendor_name = managed_device.manufacturer

            if managed_device.compliance_state:
                is_compliant = managed_device.compliance_state.value == "compliant"
            if managed_device.managed_device_owner_type:
                is_personal = managed_device.managed_device_owner_type.value == "personal"
            is_supervised = managed_device.is_supervised

            # Use managed device OS version if richer
            if managed_device.os_version:
                os_name = managed_device.os_version

        if not network_interfaces and machine.ipAddresses:
            interfaces = []
            for iface in machine.ipAddresses:
                mac = iface.get("macAddress")
                ip_addr = iface.get("ipAddress")
                iface_type = (iface.get("type") or "").lower()
                type_str, type_id = NETWORK_INTERFACE_TYPE_MAP.get(
                    iface_type, (NetworkInterfaceTypeStr.OTHER, NetworkInterfaceTypeId.OTHER)
                )
                if mac or ip_addr:
                    interfaces.append(
                        NetworkInterface(mac=mac, ip=ip_addr, name=iface_type or None, type=type_str, type_id=type_id)
                    )
            if interfaces:
                network_interfaces = interfaces

        return Device(
            type_id=device_type_id,
            type=device_type_str,
            uid=machine.id,
            uid_alt=uid_alt,
            hostname=machine.computerDnsName or "",
            ip=machine.lastIpAddress,
            os=OperatingSystem(
                name=os_name,
                type=os_type_str,
                type_id=os_type_id,
            ),
            model=model,
            vendor_name=vendor_name,
            first_seen_time=first_seen_time,
            last_seen_time=last_seen_time,
            imei_list=imei_list,
            meid=meid,
            iccid=iccid,
            udid=udid,
            groups=groups,
            network_interfaces=network_interfaces,
            is_compliant=is_compliant,
            is_managed=True,
            is_personal=is_personal,
            is_supervised=is_supervised,
            risk_level=risk_level_str,
            risk_level_id=risk_level_id,
        )

    def build_enrichments(
        self,
        machine: DefenderMachine,
        managed_device: ManagedDevice | None = None,
    ) -> list[DeviceEnrichmentObject] | None:
        enrichments = []
        if machine.aadDeviceId:
            enrichments.append(DeviceEnrichmentObject(name="azure_ad_device_id", value=machine.aadDeviceId))
        if machine.healthStatus:
            enrichments.append(DeviceEnrichmentObject(name="health_status", value=machine.healthStatus))
        if machine.exposureLevel:
            enrichments.append(DeviceEnrichmentObject(name="exposure_level", value=machine.exposureLevel))
        if machine.rbacGroupName:
            enrichments.append(DeviceEnrichmentObject(name="rbac_group_name", value=machine.rbacGroupName))

        if managed_device:
            if managed_device.user_principal_name:
                enrichments.append(
                    DeviceEnrichmentObject(name="user_principal_name", value=managed_device.user_principal_name)
                )
            if managed_device.management_agent:
                enrichments.append(
                    DeviceEnrichmentObject(name="management_agent", value=managed_device.management_agent.value)
                )

        return enrichments if enrichments else None

    def map_to_ocsf(
        self,
        machine: DefenderMachine,
        managed_device: ManagedDevice | None = None,
    ) -> DeviceOCSFModel:
        device = self.build_device_from_machine(machine, managed_device)
        enrichments = self.build_enrichments(machine, managed_device)

        event_time: float = datetime.now().timestamp()
        if machine.lastSeen:
            event_time = isoparse(machine.lastSeen).timestamp()
        elif machine.firstSeen:
            event_time = isoparse(machine.firstSeen).timestamp()

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

    def _fetch_machines(self) -> list[DefenderMachine]:
        """Fetch all machines from Defender for Endpoint API with pagination."""
        machines: list[DefenderMachine] = []
        endpoint = self.MACHINES_ENDPOINT
        if self.most_recent_date_seen:
            params = urlencode({"$filter": f"lastSeen gt {self.most_recent_date_seen}"})
            endpoint = f"{endpoint}?{params}"
        url: str | None = urljoin(self.defender_client.base_url, endpoint)

        while url and self.running:
            try:
                response = self.defender_client.get(url)
                response.raise_for_status()
            except Exception as e:
                self.log(message=f"Error fetching machines: {e}", level="error")
                break

            data = response.json()
            page = DefenderMachineListResponse.model_validate(data)
            machines.extend(page.value)
            url = page.odata_next_link

        return machines

    async def _fetch_managed_device_by_aad_id(
        self, client: GraphServiceClient, aad_device_id: str
    ) -> ManagedDevice | None:
        """Fetch a managed device from Graph API by its Azure AD device ID."""
        query_params = ManagedDevicesRequestBuilder.ManagedDevicesRequestBuilderGetQueryParameters(
            filter=f"azureADDeviceId eq '{aad_device_id}'",
            top=1,
        )
        request_config = RequestConfiguration(
            query_parameters=query_params,
        )

        try:
            response = await client.device_management.managed_devices.get(
                request_configuration=request_config,
            )
            if response and response.value:
                return response.value[0]
        except Exception as e:
            self.log(message=f"Error fetching managed device for aadDeviceId={aad_device_id}: {e}", level="warning")

        return None

    async def get_assets(self) -> AsyncGenerator[DeviceOCSFModel, None]:
        """Yield OCSF DeviceOCSFModel: fetch Defender machines, enrich with Graph managed devices."""
        most_recent_raw: str | None = None

        machines = self._fetch_machines()

        async with self._graph_client() as client:
            for machine in machines:
                if not self.running:
                    break

                # Enrich with managed device data if aadDeviceId available
                managed_device: ManagedDevice | None = None
                if machine.aadDeviceId:
                    managed_device = await self._fetch_managed_device_by_aad_id(client, machine.aadDeviceId)

                try:
                    ocsf_device = self.map_to_ocsf(machine, managed_device)
                except Exception as e:
                    self.log(
                        message=f"Error mapping device {machine.id}: {e}",
                        level="warning",
                    )
                    continue

                # Track most recent lastSeen for checkpoint
                if machine.lastSeen:
                    if most_recent_raw is None or machine.lastSeen > most_recent_raw:
                        most_recent_raw = machine.lastSeen

                yield ocsf_device

        self._latest_time_raw = most_recent_raw

    async def update_checkpoint(self) -> None:
        if self._latest_time_raw:
            with self.context as cache:
                cache["most_recent_date_seen"] = self._latest_time_raw
