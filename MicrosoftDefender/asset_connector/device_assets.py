from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from functools import cached_property
from urllib.parse import urlencode, urljoin

from azure.identity.aio import ClientSecretCredential
from kiota_abstractions.base_request_configuration import RequestConfiguration
from msgraph import GraphServiceClient
from msgraph.generated.device_management.managed_devices.managed_devices_request_builder import (
    ManagedDevicesRequestBuilder,
)
from msgraph.generated.models.managed_device import ManagedDevice
from sekoia_automation.asset_connector import AsyncAssetConnector
from sekoia_automation.asset_connector.models.ocsf.base import Metadata, Product
from sekoia_automation.asset_connector.models.ocsf.device import DeviceOCSFModel
from sekoia_automation.storage import PersistentJSON

from asset_connector.mappers import DeviceMapper, MissingHostnameError
from asset_connector.models import DefenderMachine, DefenderMachineListResponse
from microsoftdefender_modules import MicrosoftDefenderModule
from microsoftdefender_modules.client import ApiClient
from microsoftdefender_modules.logging import get_logger

logger = get_logger(__name__)

GRAPH_SCOPES: list[str] = ["https://graph.microsoft.com/.default"]


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

    def map_to_ocsf(
        self,
        machine: DefenderMachine,
        managed_device: ManagedDevice | None = None,
    ) -> DeviceOCSFModel:
        mapper = DeviceMapper(machine, managed_device)

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
            time=mapper.build_event_time(),
            metadata=self.metadata,
            device=mapper.build_device(),
            enrichments=mapper.build_enrichments(),
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
                raise

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
        generated = 0
        skipped = 0

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
                except MissingHostnameError as e:
                    self.log(message=f"Skipping device: {e}", level="warning")
                    skipped += 1
                    # Still move the cursor past it so it is not re-fetched and re-warned every cycle
                    if machine.lastSeen and (most_recent_raw is None or machine.lastSeen > most_recent_raw):
                        most_recent_raw = machine.lastSeen
                    continue
                except Exception as e:
                    self.log(
                        message=f"Error mapping device {machine.id}: {e}",
                        level="warning",
                    )
                    skipped += 1
                    continue

                # Track most recent lastSeen for checkpoint
                if machine.lastSeen:
                    if most_recent_raw is None or machine.lastSeen > most_recent_raw:
                        most_recent_raw = machine.lastSeen

                generated += 1
                yield ocsf_device

        self.log(message=f"Device assets: {generated} generated, {skipped} skipped", level="info")
        if self.running:
            self._latest_time_raw = most_recent_raw

    async def update_checkpoint(self) -> None:
        if self._latest_time_raw:
            with self.context as cache:
                cache["most_recent_date_seen"] = self._latest_time_raw
