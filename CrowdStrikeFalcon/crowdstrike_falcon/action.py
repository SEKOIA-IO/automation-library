from functools import cached_property

from sekoia_automation.action import Action

from crowdstrike_falcon import CrowdStrikeFalconModule
from crowdstrike_falcon.client import CrowdstrikeFalconClient


class CrowdstrikeAction(Action):
    module: CrowdStrikeFalconModule

    @cached_property
    def _http_default_headers(self) -> dict[str, str]:
        """
        Return the default headers for the HTTP requests used in this connector.

        Returns:
            dict[str, str]:
        """
        return {
            "User-Agent": "sekoiaio-connector/{0}-{1}".format(
                self.module.manifest.get("slug"), self.module.manifest.get("version")
            ),
        }

    @cached_property
    def client(self) -> CrowdstrikeFalconClient:
        return CrowdstrikeFalconClient(
            self.module.configuration.base_url,
            self.module.configuration.client_id,
            self.module.configuration.client_secret,
            default_headers=self._http_default_headers,
        )
