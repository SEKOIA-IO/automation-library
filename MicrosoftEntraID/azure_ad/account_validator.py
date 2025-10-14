import asyncio
from functools import cached_property

from azure.identity.aio import ClientSecretCredential  # async credentials only
from kiota_authentication_azure.azure_identity_authentication_provider import AzureIdentityAuthenticationProvider
from msgraph import GraphRequestAdapter, GraphServiceClient
from sekoia_automation.account_validator import AccountValidator


class AzureADAccountValidator(AccountValidator):
    _client: GraphServiceClient | None = None

    @cached_property
    def client(self) -> GraphServiceClient:  # pragma: no cover
        if self._client is None:
            credentials = ClientSecretCredential(
                tenant_id=self.module.configuration["tenant_id"],
                client_id=self.module.configuration["client_id"],
                client_secret=self.module.configuration["client_secret"],
            )
            auth_provider = AzureIdentityAuthenticationProvider(credentials)
            adapter = GraphRequestAdapter(auth_provider)
            self._client = GraphServiceClient(request_adapter=adapter)

        return self._client

    def validate(self) -> bool:
        try:
            loop = asyncio.get_event_loop()
            loop.run_until_complete(self.client.users.get())
        except Exception as e:
            self.error(f"Impossible to connect to the Azure AD tenant: {e}")
            return False
        return True
