from functools import cached_property

from flareio import FlareApiClient
from sekoia_automation.account_validator import AccountValidator

from flareio_modules import FlareIOModule


class FlareAccountValidator(AccountValidator):
    module: FlareIOModule

    @cached_property
    def client(self) -> FlareApiClient:
        return FlareApiClient(
            api_key=self.module.configuration.api_key,
            tenant_id=self.module.configuration.tenant_id,
        )

    def validate(self) -> bool:
        try:
            response = self.client.get("/tokens/test")
        except Exception as error:
            self.log(f"Error while validating account: {error}", level="error")
            return False

        if not response.ok:
            self.log(
                f"Error while validating account. Authentication failed with status {response.status_code}",
                level="error",
            )
            return False

        return True
