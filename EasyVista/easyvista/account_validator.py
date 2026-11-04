from requests.exceptions import RequestException
from sekoia_automation.account_validator import AccountValidator

from easyvista.client import TIMEOUT, ApiClient


class EasyVistaAccountValidator(AccountValidator):
    """Validate the EasyVista credentials by reading one asset."""

    def validate(self) -> bool:
        client = ApiClient.from_configuration(self.module.configuration, nb_retries=0)
        url = f"{client.api_url}/assets"
        try:
            response = client.get(url, params={"max_rows": 1}, timeout=TIMEOUT)
        except RequestException as error:
            message = f"Unable to reach EasyVista at {url}: {error}"
        else:
            if response.ok:
                self.log(message="EasyVista credentials validated successfully", level="info")
                return True
            message = f"EasyVista answered HTTP {response.status_code} at {url}: {response.text[:500]}"

        self.log(message=message, level="error")
        self.error(message)
        return False
