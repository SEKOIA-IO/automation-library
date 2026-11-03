from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from azure.identity.aio import ClientSecretCredential
from kiota_abstractions.api_error import APIError
from kiota_abstractions.base_request_configuration import RequestConfiguration
from msgraph import GraphServiceClient
from msgraph.generated.device_management.managed_devices.managed_devices_request_builder import (
    ManagedDevicesRequestBuilder,
)
from msgraph.generated.models.managed_device import ManagedDevice

from microsoftdefender_modules.models import MicrosoftDefenderModuleConfiguration

GRAPH_SCOPES: list[str] = ["https://graph.microsoft.com/.default"]

# Graph statuses that will not go away on the next cycle
PERMANENT_GRAPH_STATUSES = {401, 403}


@asynccontextmanager
async def graph_client(
    configuration: MicrosoftDefenderModuleConfiguration,
) -> AsyncGenerator[GraphServiceClient, None]:
    async with ClientSecretCredential(
        tenant_id=configuration.tenant_id,
        client_id=configuration.app_id,
        client_secret=configuration.app_secret,
    ) as credential:
        yield GraphServiceClient(credentials=credential, scopes=GRAPH_SCOPES)


async def fetch_managed_device(client: GraphServiceClient, aad_device_id: str) -> ManagedDevice | None:
    """Fetch the Intune managed device of an Azure AD device id. Raises when the Graph call fails."""
    query_params = ManagedDevicesRequestBuilder.ManagedDevicesRequestBuilderGetQueryParameters(
        filter=f"azureADDeviceId eq '{aad_device_id}'",
        top=1,
    )
    request_config = RequestConfiguration(
        query_parameters=query_params,
    )

    response = await client.device_management.managed_devices.get(
        request_configuration=request_config,
    )
    if response and response.value:
        return response.value[0]
    return None


def is_transient_graph_error(error: Exception) -> bool:
    """Tell whether a failed Graph lookup may succeed on the next cycle."""
    return not (isinstance(error, APIError) and error.response_status_code in PERMANENT_GRAPH_STATUSES)
