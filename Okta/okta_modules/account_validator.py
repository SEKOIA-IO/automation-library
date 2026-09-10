import asyncio
from functools import cached_property

from okta.client import Client as OktaClient
from sekoia_automation.account_validator import AccountValidator

from okta_modules import OktaModule


class OktaAccountValidator(AccountValidator):
    module: OktaModule

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

    def validate(self) -> bool:
        try:
            loop = asyncio.get_event_loop()
            _, _, err = loop.run_until_complete(self.client.list_users())
            if not err:
                return True

            # Okta errors expose `.message`, but it is empty on the base `Error` class.
            # Network failures are returned as raw exceptions, some of which stringify to "".
            message = getattr(err, "message", "") or str(err) or repr(err)
        except Exception as e:
            message = str(e) or repr(e)

        error_message = f"Error while validating account. Authentication failed: {message}"
        self.log(error_message, level="error")
        # Without this the platform has no error to display and falls back to "Unknown error"
        self.error(error_message)

        return False
