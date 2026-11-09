import requests
from sekoia_automation.account_validator import AccountValidator

from thor_cloud_modules import ThorCloudModule, client


class ThorCloudAccountValidator(AccountValidator):
    """Check that the API key is accepted by THOR Cloud or THOR Cloud Lite.

    The account only holds the API key; the product is chosen per intake or action.
    The key is therefore valid when one of the two services accepts it.
    """

    module: ThorCloudModule

    def validate(self) -> bool:
        api_key = self.module.configuration.api_key
        if not api_key:
            self.error("The THOR Cloud API key is empty")
            return False

        headers = client.get_headers(api_key)
        failures: list[str] = []
        for product, base_url in client.ENDPOINTS.items():
            try:
                client.check_api_key(base_url, headers)
                return True
            except requests.HTTPError as error:
                failures.append(f"{product}: HTTP {error.response.status_code}")
            except requests.RequestException as error:
                failures.append(f"{product}: {error.__class__.__name__}")

        self.error(
            "The API key was rejected by THOR Cloud and THOR Cloud Lite ("
            + "; ".join(failures)
            + "). Check the key and that it is allowed to list scans."
        )
        return False
