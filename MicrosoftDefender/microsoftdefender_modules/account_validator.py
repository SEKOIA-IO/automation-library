from functools import cached_property
from urllib.parse import urljoin

from sekoia_automation.account_validator import AccountValidator

from microsoftdefender_modules import MicrosoftDefenderModule
from microsoftdefender_modules.client import ApiClient


class MicrosoftDefenderAccountValidator(AccountValidator):
    module: MicrosoftDefenderModule

    @cached_property
    def client(self) -> ApiClient:  # pragma: no cover
        return ApiClient(
            base_url=self.module.configuration.base_url,
            app_id=self.module.configuration.app_id,
            app_secret=self.module.configuration.app_secret,
            tenant_id=self.module.configuration.tenant_id,
        )

    def validate(self) -> bool:
        try:
            url = urljoin(self.client.base_url, "/api/machines?$top=1")
            response = self.client.get(url)
            response.raise_for_status()
        except Exception as e:
            self.error(f"Failed to validate Microsoft Defender credentials: {e}")
            return False
        return True
