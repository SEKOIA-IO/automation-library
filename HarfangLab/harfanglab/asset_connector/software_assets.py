from collections.abc import Generator
from datetime import datetime, timedelta
from functools import cached_property
from typing import Optional
from urllib.parse import urljoin

from dateutil.parser import isoparse
from pydantic.v1 import ValidationError
from requests.exceptions import RequestException
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
    SoftwareOCSFModel,
    SoftwarePackage,
)
from sekoia_automation.storage import PersistentJSON

from harfanglab.asset_connector.models import HarfanglabAgent, HarfanglabApplication
from harfanglab.client import ApiClient
from harfanglab.helpers import handle_uri


class HarfanglabSoftwareAssetConnector(AssetConnector):

    # Configuration Constants
    AGENT_ENDPOINT: str = "/api/data/endpoint/Agent"
    APPLICATION_ENDPOINT_TEMPLATE: str = "/api/data/endpoint/Agent/{agent_uid}/applications/"
    DEVICE_ORDERING_FIELD: str = "firstseen"
    PRODUCT_NAME: str = "Harfanglab EDR"
    PRODUCT_VERSION: str = "24.12"
    METADATA_VERSION: str = "1.5.0"
    DEFAULT_LIMIT: int = 1000

    # OCSF Constants
    ACTIVITY_ID: int = 2
    ACTIVITY_NAME: str = "Collect"
    CATEGORY_NAME: str = "Discovery"
    CATEGORY_UID: int = 5
    CLASS_NAME: str = "Software Inventory Info"
    CLASS_UID: int = 5020
    TYPE_NAME: str = "Software Inventory Info: Collect"
    TYPE_UID: int = 502002

    # Application type mapping
    APP_TYPE_MAP: dict[str, tuple[PackageTypeStr, PackageTypeId]] = {
        "uwp": (PackageTypeStr.APPLICATION, PackageTypeId.APPLICATION),
        "win32": (PackageTypeStr.APPLICATION, PackageTypeId.APPLICATION),
        "macos": (PackageTypeStr.APPLICATION, PackageTypeId.APPLICATION),
        "linux": (PackageTypeStr.APPLICATION, PackageTypeId.APPLICATION),
        "os": (PackageTypeStr.OPERATINGSYSTEM, PackageTypeId.OPERATINGSYSTEM),
    }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.context = PersistentJSON("software_context.json", self._data_path)

    @property
    def most_recent_date_seen(self) -> str | None:
        with self.context as cache:
            return cache.get("most_recent_date_seen")

    @cached_property
    def base_url(self) -> str:
        return handle_uri(self.module.configuration["url"])

    @cached_property
    def client(self) -> ApiClient:
        return ApiClient(token=self.module.configuration["api_token"], instance_url=self.base_url)

    @staticmethod
    def extract_timestamp(agent: HarfanglabAgent) -> datetime:
        return isoparse(agent.firstseen)

    @staticmethod
    def extract_os_type(os_type: str | None) -> str:
        if not os_type:
            return "UNKNOWN"

        normalized_os = os_type.strip().upper()
        valid_types = {member.name for member in OSTypeStr}

        if normalized_os not in valid_types:
            return "OTHER"

        return normalized_os

    @cached_property
    def metadata(self) -> Metadata:
        return Metadata(
            product=Product(name=self.PRODUCT_NAME, version=self.PRODUCT_VERSION), version=self.METADATA_VERSION
        )

    def build_operating_system(self, os_product_type: Optional[str], os_type: Optional[str]) -> OperatingSystem:
        os_type = self.extract_os_type(os_type)
        return OperatingSystem(name=os_product_type, type=OSTypeStr[os_type], type_id=OSTypeId[os_type])

    def build_device(self, agent: HarfanglabAgent) -> Device:
        """
        Build a minimal Device object for software OCSF model.
        Args:
            agent (HarfanglabAgent): Harfanglab agent data.
        Returns:
            Device: Mapped OCSF Device object.
        """
        first_seen_time = None
        last_seen_time = None

        try:
            if agent.firstseen:
                first_seen_time = isoparse(agent.firstseen).timestamp()
            if agent.lastseen:
                last_seen_time = isoparse(agent.lastseen).timestamp()
        except (ValueError, TypeError) as e:
            self.log(f"Error parsing timestamps for asset {agent.id}: {e}", level="warning")

        return Device(
            type_id=DeviceTypeId.DESKTOP,
            type=DeviceTypeStr.DESKTOP,
            uid=agent.id,
            os=self.build_operating_system(agent.osproducttype, agent.ostype),
            hostname=agent.hostname,
            domain=agent.domainname,
            ip=agent.ipaddress,
            first_seen_time=first_seen_time,
            last_seen_time=last_seen_time,
        )

    def build_software_package(self, app: HarfanglabApplication) -> SoftwarePackage:
        """
        Build a SoftwarePackage from a Harfanglab application.
        Args:
            app (HarfanglabApplication): Application data from Harfanglab.
        Returns:
            SoftwarePackage: Mapped OCSF SoftwarePackage.
        """
        app_type = (app.app_type or "").lower()
        pkg_type, pkg_type_id = self.APP_TYPE_MAP.get(app_type, (PackageTypeStr.UNKNOWN, PackageTypeId.UNKNOWN))

        return SoftwarePackage(
            name=app.name,
            version=app.last_version or app.first_version or "unknown",
            uid=app.id,
            cpe_name=app.cpe_prefix,
            type=pkg_type,
            type_id=pkg_type_id,
        )

    def map_software_fields(
        self, agent: HarfanglabAgent, app: HarfanglabApplication, device: Device
    ) -> SoftwareOCSFModel:
        """
        Map a Harfanglab application to an OCSF SoftwareOCSFModel.
        Args:
            agent (HarfanglabAgent): The agent the application belongs to.
            app (HarfanglabApplication): Application data from Harfanglab.
            device (Device): Pre-built OCSF Device for the agent.
        Returns:
            SoftwareOCSFModel: Mapped OCSF software model.
        """
        return SoftwareOCSFModel(
            activity_id=self.ACTIVITY_ID,
            activity_name=self.ACTIVITY_NAME,
            category_name=self.CATEGORY_NAME,
            category_uid=self.CATEGORY_UID,
            class_name=self.CLASS_NAME,
            class_uid=self.CLASS_UID,
            type_name=self.TYPE_NAME,
            type_uid=self.TYPE_UID,
            time=self.extract_timestamp(agent).timestamp(),
            metadata=self.metadata,
            device=device,
            sbom=SoftwareBillOfMaterials(
                package=self.build_software_package(app),
            ),
        )

    def _fetch_devices(self, from_date: str | None) -> Generator[list[HarfanglabAgent], None, None]:
        """
        Fetch devices from Harfanglab API with pagination.
        Args:
            from_date (str | None): ISO 8601 formatted date string to filter devices.
        Yields:
            Generator[list[HarfanglabAgent]]: Generator yielding lists of parsed agent objects.
        """
        self.log(f"Fetching devices from Harfanglab API - Start date: {from_date or 'beginning'}", level="info")

        current_url = urljoin(self.base_url, self.AGENT_ENDPOINT)
        params: dict[str, str | int] = {
            "ordering": self.DEVICE_ORDERING_FIELD,
            "limit": self.DEFAULT_LIMIT,
        }

        if from_date:
            params["firstseen"] = from_date

        try:
            device_response = self.client.get(current_url, params=params)
            device_response.raise_for_status()

            while self.running:
                raw_page = device_response.json()
                count = raw_page.get("count", 0)

                if not raw_page or count == 0:
                    self.log("No more devices to fetch", level="info")
                    return

                agents: list[HarfanglabAgent] = []
                for item in raw_page.get("results", []):
                    try:
                        agents.append(HarfanglabAgent.parse_obj(item))
                    except ValidationError as e:
                        self.log(
                            f"Skipping device (ID: {item.get('id', 'unknown')}) due to validation error: {e}",
                            level="warning",
                        )

                yield agents

                next_page = raw_page.get("next")
                if not next_page:
                    return

                current_url = urljoin(self.base_url, next_page)
                device_response = self.client.get(current_url)
                device_response.raise_for_status()

        except RequestException as e:
            self.log(f"API request failed - URL: {current_url}, Error: {str(e)}", level="error")
            raise

    def _fetch_applications(self, agent_uid: str) -> Generator[list[HarfanglabApplication], None, None]:
        """
        Fetch applications installed on a specific agent.
        Args:
            agent_uid (str): The agent UID to fetch applications for.
        Yields:
            Generator[list[HarfanglabApplication]]: Generator yielding lists of application objects.
        """
        endpoint = self.APPLICATION_ENDPOINT_TEMPLATE.format(agent_uid=agent_uid)
        current_url = urljoin(self.base_url, endpoint)
        params: dict[str, str | int] = {"limit": self.DEFAULT_LIMIT}

        try:
            app_response = self.client.get(current_url, params=params)
            app_response.raise_for_status()

            while self.running:
                raw_page = app_response.json()
                count = raw_page.get("count", 0)

                if not raw_page or count == 0:
                    return

                apps: list[HarfanglabApplication] = []
                for item in raw_page.get("results", []):
                    try:
                        apps.append(HarfanglabApplication.parse_obj(item))
                    except ValidationError as e:
                        self.log(
                            f"Skipping application (ID: {item.get('id', 'unknown')}) " f"due to validation error: {e}",
                            level="warning",
                        )

                yield apps

                next_page = raw_page.get("next")
                if not next_page:
                    return

                current_url = urljoin(self.base_url, next_page)
                app_response = self.client.get(current_url)
                app_response.raise_for_status()

        except RequestException as e:
            self.log(
                f"Failed to fetch applications for agent {agent_uid}: {str(e)}",
                level="warning",
            )

    def iterate_devices(self) -> Generator[list[HarfanglabAgent], None, None]:
        """
        Iterate over devices fetched from the Harfanglab API, updating the checkpoint timestamp.
        Yields:
            Generator[list[HarfanglabAgent]]: Generator yielding lists of agent objects.
        """
        orig_date = isoparse(self.most_recent_date_seen) if self.most_recent_date_seen else None
        max_date: datetime | None = None

        self.log(f"Starting device iteration - Checkpoint date: {self.most_recent_date_seen or 'None'}", level="info")

        device_count = 0

        try:
            for agents in self._fetch_devices(from_date=self.most_recent_date_seen):
                if not agents:
                    continue

                device_count += len(agents)

                last_agent = max(agents, key=self.extract_timestamp)
                last_ts = self.extract_timestamp(last_agent)
                candidate = last_ts + timedelta(microseconds=1)

                if max_date is None or candidate > max_date:
                    max_date = candidate

                yield agents

            self.log(f"Device iteration complete - Total devices processed: {device_count}", level="info")

            if max_date and (orig_date is None or max_date > orig_date):
                self._latest_time = max_date.isoformat()

        except Exception as e:
            self.log(f"Device iteration failed - Error: {str(e)}, Devices processed: {device_count}", level="error")
            raise

    def update_checkpoint(self) -> None:
        if self._latest_time:
            with self.context as cache:
                cache["most_recent_date_seen"] = self._latest_time

            self.log(f"Checkpoint updated successfully - New timestamp: {self._latest_time}", level="debug")
        else:
            self.log("No checkpoint update needed - No new timestamp available", level="debug")

    def get_assets(self) -> Generator[SoftwareOCSFModel, None, None]:
        self.log(f"Software asset generation started - Data path: {self._data_path.absolute()}", level="info")

        software_generated = 0
        assets_skipped = 0

        try:
            for agents in self.iterate_devices():
                for agent in agents:
                    try:
                        device = self.build_device(agent)
                    except (KeyError, ValueError) as e:
                        assets_skipped += 1
                        self.log(
                            f"Device build skipped - ID: {agent.id}, Hostname: {agent.hostname}, Reason: {str(e)}",
                            level="warning",
                        )
                        continue

                    for apps in self._fetch_applications(agent.id):
                        for app in apps:
                            try:
                                yield self.map_software_fields(agent, app, device)
                                software_generated += 1
                            except (KeyError, ValueError) as e:
                                assets_skipped += 1
                                self.log(
                                    f"Software asset skipped - Agent: {agent.id}, "
                                    f"App: {app.name}, Reason: {str(e)}",
                                    level="warning",
                                )
                                continue

            self.log(
                f"Software asset generation completed - Total generated: {software_generated}, "
                f"Skipped: {assets_skipped}",
                level="info",
            )

        except Exception as e:
            self.log(
                f"Software asset generation failed - Generated: {software_generated}, "
                f"Skipped: {assets_skipped}, Error: {str(e)}",
                level="error",
            )
            raise
