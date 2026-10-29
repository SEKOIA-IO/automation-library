from requests.exceptions import RequestException, Timeout
from sekoia_automation.account_validator import AccountValidator

from nozomi_networks import NozomiModule
from nozomi_networks.asset_connector.client import NozomiQueryClient, NozomiQueryError


class NozomiAccountValidator(AccountValidator):
    """Validate Nozomi Networks credentials by performing a Guardian/CMC Open API sign-in (``/api/open/sign_in``)."""

    module: NozomiModule

    TIMEOUT = 30

    def _fail(self, message: str) -> bool:
        message = f"Impossible to authenticate to the Nozomi Networks API: {message}"
        self.log(message=message, level="error")
        self.error(message)
        return False

    def validate(self) -> bool:
        base_url = str(self.module.configuration.base_url).rstrip("/")
        url = f"{base_url}{NozomiQueryClient.SIGN_IN_ENDPOINT}"
        client = NozomiQueryClient(
            key_name=self.module.configuration.key_name,
            key_token=self.module.configuration.key_token,
            base_url=base_url,
            timeout=self.TIMEOUT,
        )
        try:
            client.refresh_authorization()
        except NozomiQueryError as error:
            if 400 <= error.status_code < 500:
                return self._fail(
                    f"client error ({error.status_code}) at {url}, check the key name and token: {error}"
                )
            if 500 <= error.status_code < 600:
                return self._fail(f"server error ({error.status_code}) at {url}: {error}")
            return self._fail(f"unexpected response ({error.status_code}) at {url}: {error}")
        except Timeout:
            return self._fail(f"timeout at {url}")
        except RequestException as error:
            return self._fail(f"network error at {url}: {error}")
        except Exception as error:
            return self._fail(f"unexpected error at {url}: {error}")
        finally:
            client.close()

        self.log(message="Nozomi Networks credentials validated successfully", level="info")
        return True
