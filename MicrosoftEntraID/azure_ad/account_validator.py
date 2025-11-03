import asyncio

from sekoia_automation.account_validator import AccountValidator
from graph_api.client import GraphApi

from azure_ad.base import AzureADModule


class AzureADAccountValidator(AccountValidator):
    module: AzureADModule
    _client: GraphApi | None = None

    @property
    def client(self) -> GraphApi:  # pragma: no cover
        if not self._client:
            self._client = GraphApi(
                tenant_id=self.module.configuration.tenant_id,
                client_id=self.module.configuration.client_id,
                client_secret=self.module.configuration.client_secret,
            )

        return self._client

    def validate(self) -> bool:
        try:
            loop = asyncio.get_event_loop()
            loop.run_until_complete(self.client.client.users.get())
        except Exception as e:
            self.error(f"Impossible to connect to the Azure AD tenant: {e}")
            return False
        return True
