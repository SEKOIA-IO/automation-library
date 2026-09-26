from sekoia_automation.account_validator import AccountValidator

from nozomi_networks import NozomiModule
from nozomi_networks.asset_connector.client import NozomiQueryClient


class NozomiAccountValidator(AccountValidator):
    """Validate Nozomi Networks credentials by performing an API sign-in."""

    module: NozomiModule

    def validate(self) -> bool:
        try:
            client = NozomiQueryClient(
                key_name=self.module.configuration.key_name,
                key_token=self.module.configuration.key_token,
                base_url=self.module.configuration.base_url,
            )
            client.refresh_authorization()
        except Exception as e:
            self.error(f"Impossible to authenticate to the Nozomi Networks API: {e}")
            return False
        return True
