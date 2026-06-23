from functools import cached_property

from sekoia_automation.account_validator import AccountValidator

from eset_modules import EsetModule
from eset_modules.client import ApiClient


class EsetAccountValidator(AccountValidator):
    module: EsetModule

    @cached_property
    def client(self) -> ApiClient:  # pragma: no cover
        region = self.module.configuration.region
        return ApiClient(
            auth_base_url=f"https://{region}.business-account.iam.eset.systems",
            username=self.module.configuration.username,
            password=self.module.configuration.password,
        )

    def validate(self) -> bool:
        try:
            region = self.module.configuration.region
            url = f"https://{region}.device-management.eset.systems/v1/devices"
            response = self.client.get(url, params={"pageSize": 1})
            response.raise_for_status()
        except Exception as e:
            self.error(f"Could not connect to ESET EDR API with the provided credentials: {e}")
            return False
        return True
