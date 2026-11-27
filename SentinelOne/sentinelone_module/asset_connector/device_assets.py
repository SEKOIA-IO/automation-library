"""SentinelOne Device Asset Connector module.

This module provides functionality to collect device assets from SentinelOne
and format them according to OCSF standards.
"""

from collections.abc import Generator, Iterator
from functools import cached_property
from typing import Any

from dateutil.parser import isoparse
from sekoia_automation.asset_connector import AssetConnector
from sekoia_automation.asset_connector.models.ocsf.base import (
    Metadata,
    Product,
)
from sekoia_automation.asset_connector.models.ocsf.device import (
    Device,
    DeviceDataObject,
    DeviceEnrichmentObject,
    DeviceOCSFModel,
    DeviceTypeId,
    DeviceTypeStr,
    GeoLocation,
    Group,
    NetworkInterface,
    OperatingSystem,
    Organization,
    OSTypeId,
    OSTypeStr,
    RiskLevelId,
    RiskLevelStr,
)

from sentinelone_module.asset_connector.checkpoint import AssetCheckpoint, Cursor
from sentinelone_module.asset_connector.models import SentinelOneAgent
from sentinelone_module.base import SentinelOneModule
from sentinelone_module.client import SentinelOneClient


class SentinelOneDeviceAssetConnector(AssetConnector):
    """Asset connector for collecting device data from SentinelOne.

    This connector fetches agent/device information from SentinelOne and formats it
    according to OCSF (Open Cybersecurity Schema Framework) standards.
    """

    module: SentinelOneModule

    # Agents are swept in full passes on createdAt: no field is known to move on every agent change
    checkpoint_field = "createdAt"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the SentinelOne Device Asset Connector.

        Args:
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.
        """
        super().__init__(*args, **kwargs)
        self.asset_checkpoint = AssetCheckpoint(self.data_path, "sweep")

    @cached_property
    def client(self) -> SentinelOneClient:
        """Get the SentinelOne HTTP client instance.

        Returns:
            Configured SentinelOneClient instance.
        """
        configuration = self.module.configuration
        return SentinelOneClient(
            hostname=configuration.hostname,
            api_token=configuration.api_token,
            rate_limit_per_second=20,  # Limit to 25 requests per second in the documentation so we set 20 to be safe
        )

    def update_checkpoint(self) -> None:
        """Commit the createdAt of the last pushed agent."""
        self.asset_checkpoint.commit()

    def reset_checkpoint(self) -> None:
        """Start a new pass over every agent."""
        self.asset_checkpoint.reset()

    def get_mapped_fields(self) -> dict[str, str]:
        return {}

    def fetch_agents(
        self, checkpoint: Cursor | None, cursor: str | None = None
    ) -> tuple[list[SentinelOneAgent], str | None]:
        """Fetch one page of agents, sorted ascending on createdAt.

        Args:
            checkpoint: Only fetch agents created strictly after this date.
            cursor: Optional cursor for pagination.

        Returns:
            Tuple of (agents list, next cursor).
        """
        params: dict[str, Any] = {"limit": 100, "sortBy": self.checkpoint_field, "sortOrder": "asc"}
        if checkpoint:
            params["createdAt__gt"] = checkpoint
        if cursor:
            params["cursor"] = cursor

        response = self.client.get("/web/api/v2.1/agents", params=params)

        if response.get("errors"):
            self.log(f"Errors in API response: {response['errors']}", level="error")

        agents = [SentinelOneAgent(**agent) for agent in response.get("data") or []]
        next_cursor = (response.get("pagination") or {}).get("nextCursor")
        return agents, next_cursor if agents else None

    def iter_agents(self, checkpoint: Cursor | None) -> Iterator[SentinelOneAgent]:
        """Stream every agent created after the checkpoint, page by page.

        A failed page raises, so the pass resumes from the checkpoint instead of being marked complete.
        """
        cursor: str | None = None
        while True:
            agents, cursor = self.fetch_agents(checkpoint, cursor)
            yield from agents
            if not cursor:
                return

    def get_device_os(self, os_type: str | None, os_name: str | None, os_revision: str | None) -> OperatingSystem:
        """Get operating system information for a device.

        Args:
            os_type: The OS type (linux, windows, macos, etc.).
            os_name: The OS name (e.g., "Windows 10", "Ubuntu").
            os_revision: The OS revision/version.

        Returns:
            OperatingSystem object with mapped OS information.
        """
        # Determine OS name for display (include version if available)
        if os_name and os_revision:
            display_name = f"{os_name} {os_revision}"
        elif os_name:
            display_name = os_name
        elif os_type:
            display_name = os_type
        else:
            display_name = "Unknown"

        # Map OS type to OCSF types
        if not os_type:
            return OperatingSystem(name=display_name, type=OSTypeStr.OTHER, type_id=OSTypeId.OTHER)

        match os_type.lower():
            case "windows":
                return OperatingSystem(name=display_name, type=OSTypeStr.WINDOWS, type_id=OSTypeId.WINDOWS)
            case "macos":
                return OperatingSystem(name=display_name, type=OSTypeStr.MACOS, type_id=OSTypeId.MACOS)
            case "linux":
                return OperatingSystem(name=display_name, type=OSTypeStr.LINUX, type_id=OSTypeId.LINUX)
            case "ios":
                return OperatingSystem(name=display_name, type=OSTypeStr.IOS, type_id=OSTypeId.IOS)
            case "android":
                return OperatingSystem(name=display_name, type=OSTypeStr.ANDROID, type_id=OSTypeId.ANDROID)
            case _:
                return OperatingSystem(name=display_name, type=OSTypeStr.OTHER, type_id=OSTypeId.OTHER)

    def get_device_type(self, machine_type: str | None) -> tuple[DeviceTypeStr, DeviceTypeId]:
        """Map SentinelOne machine type to OCSF device type.

        Args:
            machine_type: The machine type from SentinelOne.

        Returns:
            Tuple of (DeviceTypeStr, DeviceTypeId).
        """
        if not machine_type:
            return DeviceTypeStr.OTHER, DeviceTypeId.OTHER

        match machine_type.lower():
            case "desktop":
                return DeviceTypeStr.DESKTOP, DeviceTypeId.DESKTOP
            case "laptop":
                return DeviceTypeStr.DESKTOP, DeviceTypeId.DESKTOP
            case "server":
                return DeviceTypeStr.SERVER, DeviceTypeId.SERVER
            case "tablet":
                return DeviceTypeStr.MOBILE, DeviceTypeId.MOBILE
            case "mobile":
                return DeviceTypeStr.MOBILE, DeviceTypeId.MOBILE
            case "virtual":
                return DeviceTypeStr.VIRTUAL, DeviceTypeId.VIRTUAL
            case _:
                return DeviceTypeStr.OTHER, DeviceTypeId.OTHER

    def map_fields(self, agent: SentinelOneAgent) -> DeviceOCSFModel:
        """Map SentinelOne agent data to OCSF format.

        Args:
            agent: SentinelOneAgent object containing device data.

        Returns:
            DeviceOCSFModel instance with mapped device data.

        Raises:
            ValueError: If required device data is missing.
        """
        # Validate required fields
        if not agent.id:
            raise ValueError("Agent ID is required")
        if not agent.computerName:
            raise ValueError("Computer name is required")

        # Determine device type
        device_type_str, device_type_id = self.get_device_type(agent.machineType)

        # Map network interfaces if available
        network_interfaces = None
        if agent.networkInterfaces:
            network_interfaces = []
            for iface in agent.networkInterfaces:
                # Get the first IP address from inet list
                ip_address = None
                if iface.inet and len(iface.inet) > 0:
                    ip_address = iface.inet[0]

                network_interfaces.append(
                    NetworkInterface(
                        name=iface.name,
                        mac=iface.physical,
                        ip=ip_address,
                        uid=iface.id,
                    )
                )

        # Parse timestamps
        timestamp = isoparse(agent.createdAt).timestamp()
        created_time = timestamp
        first_seen_time = isoparse(agent.registeredAt).timestamp() if agent.registeredAt else None
        last_seen_time = isoparse(agent.lastActiveDate).timestamp() if agent.lastActiveDate else None
        boot_time = isoparse(agent.osStartTime).timestamp() if agent.osStartTime else None

        # Build groups list if available
        groups = None
        if agent.groupName or agent.groupId:
            groups = [
                Group(
                    name=agent.groupName or "Unknown",
                    uid=agent.groupId or agent.groupName or "unknown",
                )
            ]

        # Build location from locations list if available
        location = None
        if agent.locations and len(agent.locations) > 0:
            # Use the first location's name as city
            location = GeoLocation(city=agent.locations[0].name)

        # Determine risk level from infection state and active threats
        if agent.infected:
            risk_level: RiskLevelStr | None = RiskLevelStr.CRITICAL
            risk_level_id: RiskLevelId | None = RiskLevelId.CRITICAL
        elif agent.activeThreats:
            risk_level = RiskLevelStr.HIGH
            risk_level_id = RiskLevelId.HIGH
        else:
            risk_level = RiskLevelStr.INFO
            risk_level_id = RiskLevelId.INFO

        # Build org from SentinelOne account
        org = None
        if agent.accountName or agent.accountId:
            org = Organization(name=agent.accountName or agent.accountId, uid=agent.accountId)

        # Create the device object with enhanced fields
        device = Device(
            hostname=agent.computerName,
            name=agent.computerName,
            uid=agent.uuid or agent.id,
            uid_alt=agent.id if agent.uuid else None,  # Use ID as alternate UID when UUID is primary
            eid=agent.externalId,
            type_id=device_type_id,
            type=device_type_str,
            os=self.get_device_os(agent.osType, agent.osName, agent.osRevision),
            location=location,
            domain=agent.domain,
            ip=agent.externalIp,
            subnet=agent.groupIp,  # Network subnet/range (e.g., "31.155.5.x")
            network_interfaces=network_interfaces,
            model=agent.modelName,
            boot_time=boot_time,
            created_time=created_time,
            first_seen_time=first_seen_time,
            last_seen_time=last_seen_time,
            is_managed=True,  # SentinelOne agents are managed by definition
            is_compliant=agent.isUpToDate if agent.isUpToDate is not None else None,
            region=agent.siteName,  # Using site name as region
            groups=groups,
            org=org,
            risk_level=risk_level,
            risk_level_id=risk_level_id,
            risk_score=agent.activeThreats,
        )

        # Build a single enrichment with all additional device information
        enrichment_parts: list[str] = []
        enrichment_data: dict[str, Any] = {}

        if agent.firewallEnabled is not None:
            firewall_status = "Enabled" if agent.firewallEnabled else "Disabled"
            enrichment_parts.append(f"Firewall: {firewall_status}")
            enrichment_data["Firewall_status"] = firewall_status

        if agent.domain:
            enrichment_parts.append(f"Domain: {agent.domain}")
            enrichment_data["Full_qualified_domain_name"] = agent.domain

        users = []
        if agent.lastLoggedInUserName:
            users.append(agent.lastLoggedInUserName)
        if agent.osUsername and agent.osUsername not in users:
            users.append(agent.osUsername)
        if users:
            enrichment_parts.append(f"Users: {', '.join(users)}")
            enrichment_data["Users"] = users

        if agent.isUpToDate is not None:
            enrichment_parts.append(f"Update Status: {'Up to Date' if agent.isUpToDate else 'Update Required'}")

        if agent.activeThreats is not None:
            enrichment_parts.append(f"Active Threats: {agent.activeThreats}")

        if agent.infected is not None:
            enrichment_parts.append(f"Infection Status: {'Infected' if agent.infected else 'Clean'}")

        enrichments: list[DeviceEnrichmentObject] = []
        if enrichment_parts:
            enrichments.append(
                DeviceEnrichmentObject(
                    name="Device Details",
                    value=", ".join(enrichment_parts),
                    data=DeviceDataObject(**enrichment_data) if enrichment_data else None,
                )
            )

        return DeviceOCSFModel(
            activity_id=2,
            activity_name="Collect",
            category_name="Discovery",
            category_uid=5,
            class_name="Device Inventory Info",
            class_uid=5001,
            device=device,
            enrichments=enrichments if enrichments else None,
            time=timestamp,
            metadata=Metadata(
                product=Product(name="SentinelOne", vendor_name="SentinelOne", version=agent.agentVersion or "N/A"),
                version="1.6.0",
            ),
            severity="Informational",
            severity_id=1,
            type_name="Device Inventory Info: Collect",
            type_uid=500102,
        )

    def get_assets(self) -> Generator[DeviceOCSFModel, None, None]:
        """Generate device assets from SentinelOne, one sweep pass per frequency.

        Yields:
            DeviceOCSFModel instances for each agent found in SentinelOne.
        """
        should_fetch, checkpoint = self.asset_checkpoint.begin(self.frequency)
        if not should_fetch:
            return

        self.log(f"Fetching SentinelOne agents created after {checkpoint}", level="info")
        agents = self.iter_agents(checkpoint)
        current = next(agents, None)
        while current is not None:
            following = next(agents, None)
            next_cursor = following.createdAt if following is not None else None
            if self.asset_checkpoint.stage(current.createdAt, next_cursor):
                self.log(
                    f"Agents are not sorted ascending on createdAt ({next_cursor} after {current.createdAt}). "
                    "The checkpoint is not moved for the rest of this cycle",
                    level="error",
                )

            try:
                asset = self.map_fields(current)
            except Exception as e:
                self.log(f"Error while mapping agent {current.id}: {e}", level="error")
            else:
                yield asset
            current = following

        self.asset_checkpoint.exhausted()
