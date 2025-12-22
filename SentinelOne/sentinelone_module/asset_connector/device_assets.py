"""SentinelOne Device Asset Connector module.

This module provides functionality to collect device assets from SentinelOne
and format them according to OCSF standards.
"""

from collections.abc import Generator
from functools import cached_property
from typing import Any, Optional

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
    OSTypeId,
    OSTypeStr,
)
from sekoia_automation.storage import PersistentJSON
from sentinelone_module.client import SentinelOneClient
from sentinelone_module.asset_connector.models import SentinelOneAgent


class SentinelOneDeviceAssetConnector(AssetConnector):
    """Asset connector for collecting device data from SentinelOne.

    This connector fetches agent/device information from SentinelOne and formats it
    according to OCSF (Open Cybersecurity Schema Framework) standards.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the SentinelOne Device Asset Connector.

        Args:
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.
        """
        super().__init__(*args, **kwargs)
        self.context = PersistentJSON("context.json", self._data_path)
        self._latest_time: Optional[str] = None

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

    @property
    def most_recent_date_seen(self) -> str | None:
        """Get the most recent date seen from the context cache.

        Returns:
            The most recent date seen as a string, or None if not set.
        """
        with self.context as cache:
            return cache.get("most_recent_date_seen", None)

    def update_checkpoint(self) -> None:
        """Update the checkpoint with the most recent date seen.

        Raises:
            ValueError: If _latest_time is None.
        """
        if self._latest_time is None:
            self.log("Warning: _latest_time is None, skipping checkpoint update", level="warning")
            return

        try:
            with self.context as cache:
                cache["most_recent_date_seen"] = self._latest_time
                self.log(f"Checkpoint updated with date: {self._latest_time}", level="info")
        except Exception as e:
            self.log(f"Failed to update checkpoint: {str(e)}", level="error")

    def get_last_created_date(self, agents: list[SentinelOneAgent]) -> str:
        """Get the last created date from the list of agents.

        Args:
            agents: List of SentinelOne agents.

        Returns:
            The last created date as a string.

        Raises:
            ValueError: If the agents list is empty.
        """
        if not agents:
            raise ValueError("Cannot get last created date from empty agents list")
        return max(agent.createdAt for agent in agents)

    def fetch_agents(self, cursor: str | None = None) -> tuple[list[SentinelOneAgent], str | None]:
        """Fetch agents from SentinelOne.

        Args:
            cursor: Optional cursor for pagination.

        Returns:
            Tuple of (agents list, next cursor) or ([], None) on error.
        """
        try:
            # Build query parameters
            params: dict[str, Any] = {"limit": 100}

            if self.most_recent_date_seen:
                params["createdAt__gt"] = self.most_recent_date_seen

            if cursor:
                params["cursor"] = cursor

            # Make API request
            response = self.client.get("/web/api/v2.1/agents", params=params)

            # Check for errors in response
            if response.get("errors"):
                self.log(f"Errors in API response: {response['errors']}", level="error")

            # Extract agents data
            agents_data = response.get("data", [])
            if not agents_data:
                self.log("No agents found in response", level="info")
                return [], None

            agents = [SentinelOneAgent(**agent) for agent in agents_data]

            # Update checkpoint with the most recent date
            if agents:
                self._latest_time = self.get_last_created_date(agents)

            # Get next cursor from pagination
            next_cursor = None
            pagination = response.get("pagination")
            if pagination:
                next_cursor = pagination.get("nextCursor")

            return agents, next_cursor

        except Exception as e:
            self.log(f"Exception while fetching agents: {e}", level="error")
            return [], None

    def list_all_agents(self) -> list[SentinelOneAgent]:
        """Fetch all agents from SentinelOne using pagination.

        Returns:
            List of all agents from SentinelOne.
        """
        all_agents = []
        cursor = None

        while True:
            agents, next_cursor = self.fetch_agents(cursor)
            all_agents.extend(agents)

            if not next_cursor:
                break

            cursor = next_cursor
            self.log(f"Fetched {len(all_agents)} agents so far, continuing with next page", level="info")

        return all_agents

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
                return DeviceTypeStr.LAPTOP, DeviceTypeId.LAPTOP
            case "server":
                return DeviceTypeStr.SERVER, DeviceTypeId.SERVER
            case "tablet":
                return DeviceTypeStr.TABLET, DeviceTypeId.TABLET
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
        boot_time = agent.osStartTime  # Keep as ISO string

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

        # Create the device object with enhanced fields
        device = Device(
            hostname=agent.computerName,
            uid=agent.uuid or agent.id,
            uid_alt=agent.id if agent.uuid else None,  # Use ID as alternate UID when UUID is primary
            type_id=device_type_id,
            type=device_type_str,
            os=self.get_device_os(agent.osType, agent.osName, agent.osRevision),
            location=location,
            domain=agent.domain,
            ip=agent.externalIp,
            subnet=agent.groupIp,  # Network subnet/range (e.g., "31.155.5.x")
            network_interfaces=network_interfaces,
            model=agent.modelName,
            vendor_name="SentinelOne",
            boot_time=boot_time,
            created_time=created_time,
            first_seen_time=first_seen_time,
            last_seen_time=last_seen_time,
            is_managed=True,  # SentinelOne agents are managed by definition
            is_compliant=agent.isUpToDate if agent.isUpToDate is not None else None,
            region=agent.siteName,  # Using site name as region
            groups=groups,
        )

        # Build enrichments for additional device information
        enrichments = []

        # Add firewall status if available
        if agent.firewallEnabled is not None:
            firewall_status = "Enabled" if agent.firewallEnabled else "Disabled"
            enrichments.append(
                DeviceEnrichmentObject(
                    name="Firewall",
                    value=firewall_status,
                    data=DeviceDataObject(Firewall_status=firewall_status),
                )
            )

        # Add user information if available
        users = []
        if agent.lastLoggedInUserName:
            users.append(agent.lastLoggedInUserName)
        if agent.osUsername and agent.osUsername not in users:
            users.append(agent.osUsername)

        if users:
            enrichments.append(
                DeviceEnrichmentObject(
                    name="Users",
                    value=", ".join(users),
                    data=DeviceDataObject(Users=users),
                )
            )

        # Add update status if available
        if agent.isUpToDate is not None:
            update_status = "Up to Date" if agent.isUpToDate else "Update Required"
            enrichments.append(
                DeviceEnrichmentObject(
                    name="Update Status",
                    value=update_status,
                    data=DeviceDataObject(),
                )
            )

        # Add active threats count if available
        if agent.activeThreats is not None:
            enrichments.append(
                DeviceEnrichmentObject(
                    name="Active Threats",
                    value=str(agent.activeThreats),
                    data=DeviceDataObject(),
                )
            )

        # Add infection status if available
        if agent.infected is not None:
            infection_status = "Infected" if agent.infected else "Clean"
            enrichments.append(
                DeviceEnrichmentObject(
                    name="Infection Status",
                    value=infection_status,
                    data=DeviceDataObject(),
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
        """Generate device assets from SentinelOne.

        Yields:
            DeviceOCSFModel instances for each agent found in SentinelOne.
        """
        self.log("Starting SentinelOne device assets generator", level="info")

        agents = self.list_all_agents()
        self.log(f"Fetched {len(agents)} agents from SentinelOne", level="info")

        for agent in agents:
            try:
                yield self.map_fields(agent)
            except Exception as e:
                agent_id = getattr(agent, "id", "unknown")
                self.log(f"Error while mapping agent {agent_id}: {e}", level="error")
                continue
