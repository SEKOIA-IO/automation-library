import requests
from functools import cached_property

from sekoia_automation.account_validator import AccountValidator

from crowdstrike_falcon.client.auth import CrowdStrikeFalconApiAuthentication


class CrowdstrikeFalconAccountValidator(AccountValidator):

    @cached_property
    def _http_default_headers(self) -> dict[str, str]:
        return {
            "User-Agent": "sekoiaio-connector/{0}-{1}".format(
                self.module.manifest.get("slug"), self.module.manifest.get("version")
            ),
        }

    @cached_property
    def auth_client(self):
        return CrowdStrikeFalconApiAuthentication(
            self.module.configuration.base_url,
            self.module.configuration.client_id,
            self.module.configuration.client_secret,
            default_headers=self._http_default_headers,
        )

    def validate(self) -> bool:
        self.log(message="Start Validation credentials process for crowdstrike asset connector", level="info")

        try:
            token = self.auth_client.get_credentials()
            if not token:
                self.log(
                    message="Failed to validated credentials for crowdstrike asset connector",
                    level="info",
                )
                return False
            self.log(
                message="Successfully validated credentials for crowdstrike asset connector",
                level="info",
            )
            return True
        except requests.HTTPError as http_err:
            self.log(message=f"HTTP error validating crowdstrike credentials: {http_err}", level="error")
            return False
        except requests.RequestException as req_err:
            self.log(message=f"Network error when contacting crowdstrike: {req_err}", level="error")
            return False
        except Exception as error:
            self.log_exception(error, message="Failed to validate crowdstrike credentials")
            return False
