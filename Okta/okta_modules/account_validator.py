from sekoia_automation.account_validator import AccountValidator
from okta.client import Client as OktaClient
from functools import cached_property
import asyncio


class OktaAccountValidator(AccountValidator):

    @cached_property
    def client(self) -> OktaClient:
        """Get the Okta client instance.

        Returns:
            Configured OktaClient instance.
        """
        config = {
            "orgUrl": self.module.configuration.base_url,
            "token": self.module.configuration.apikey,
        }
        return OktaClient(config)

    def validate(self):
        try:
            loop = asyncio.get_event_loop()
            loop.run_until_complete(self.client.list_users())
        except Exception as e:
            self.log(f"Error while validating account: {e}", level="error")
            return False
        return True
