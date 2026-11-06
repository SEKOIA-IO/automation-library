from requests.exceptions import RequestException
from sekoia_automation.account_validator import AccountValidator

from easyvista.client import TIMEOUT, ApiClient, EasyVistaError, response_error

# The REST API profile may allow only some routes: the account is valid when one of them answers
CHECKS: tuple[tuple[str, dict[str, str | int]], ...] = (
    ("requests", {"max_rows": 1, "fields": "rfc_number"}),
    ("assets", {"max_rows": 1, "fields": "asset_id"}),
)


class EasyVistaAccountValidator(AccountValidator):
    """Validate the EasyVista credentials by reading one request, else one asset."""

    def _check(self) -> str | None:
        """Return the reason of the failure, None when the account is valid."""
        try:
            client = ApiClient.from_configuration(self.module.configuration, nb_retries=0)
        except EasyVistaError as error:
            return str(error)

        message = None
        for resource, params in CHECKS:
            try:
                response = client.get(f"{client.api_url}/{resource}", params=params, timeout=TIMEOUT)
            except RequestException as exception:
                return f"Unable to reach EasyVista at {client.api_url}: {exception}"

            reason = response_error(response)
            if reason is None:
                return None
            if response.status_code == 401:
                return f"Authentication failed (check credentials / tenant_id): {reason}"
            message = f"EasyVista answered {reason} on GET /{resource}"
            if response.status_code != 403:
                return message
        return message

    def validate(self) -> bool:
        message = self._check()
        if message is None:
            self.log(message="EasyVista credentials validated successfully", level="info")
            return True

        self.log(message=message, level="error")
        self.error(message)
        return False
