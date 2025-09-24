import time
import requests

from tenable.io import TenableIO
from restfly.errors import UnauthorizedError, ForbiddenError
from requests.exceptions import SSLError

from sekoia_automation.account_validator import AccountValidator


class TenableAccountValidator(AccountValidator):

    TIMEOUT = 10

    @property
    def client(self) -> TenableIO:
        """
        Create and return a TenableIO client instance using the provided configuration.

        :return:
            TenableIO: An instance of the TenableIO client configured with the base URL, access key, and secret key.
        """
        return TenableIO(
            url=self.module.configuration.base_url,
            access_key=self.module.configuration.access_key,
            secret_key=self.module.configuration.secret_key,
        )

    def validate(self) -> bool:
        since = int(time.time())

        try:
            # Use the same sdk method to check credentials
            self.client.exports.vulns(since=since, timeout=self.TIMEOUT)
            self.log(
                message="Successfully validated credentials for Tenable asset connector",
                level="info",
            )
            return True
        except UnauthorizedError as unauth_err:
            self.log(
                message=f"Unauthorized: invalid Tenable.io credentials - {unauth_err}",
                level="error",
            )
            return False
        except ForbiddenError as forbidden_err:
            self.log(
                message=f"Forbidden: insufficient permissions for Tenable.io credentials - {forbidden_err}",
                level="error",
            )
            return False
        except SSLError as ssl_err:
            self.log(message=f"SSL error connecting to Tenable.io: : {ssl_err}", level="error")
            return False
        except requests.HTTPError as http_err:
            self.log(message=f"HTTP error validating Tenable.io credentials: {http_err}", level="error")
            return False
        except requests.RequestException as req_err:
            self.log(message=f"Network error when contacting Tenable.io: {req_err}", level="error")
            return False
