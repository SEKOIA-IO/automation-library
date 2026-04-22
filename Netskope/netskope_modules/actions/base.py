from functools import cached_property
import json

from sekoia_automation.action import Action
import requests
from requests import Response

from netskope_modules.logging import get_logger

logger = get_logger()


class NetskopeAction(Action):

    @cached_property
    def api_key(self):
        return self.module.configuration.get("api_key")

    @cached_property
    def base_url(self):
        return self.module.configuration["base_url"].rstrip("/")

    def get_api_url(self, endpoint: str) -> str:
        return f"{self.base_url}/{endpoint}"

    def _handle_response_error(self, response: Response) -> None:
        if not response.ok:
            logger.error(
                "Failed request to Netskope API",
                status_code=response.status_code,
                reason=response.reason,
                error=response.content,
            )

            message = f"Request to Netskope API failed with status {response.status_code} - {response.reason}"
            self.log(message=message, level="error")
            response.raise_for_status()

        try:
            json_body = response.json()
            if "error" in json_body:
                error_message = json_body["error"].get("message", "Unknown error")
                logger.error(
                    "Netskope API returned an error",
                    error=error_message,
                    status_code=response.status_code,
                )
                raise ValueError(f"Netskope API returned an error: {error_message}")
        except json.JSONDecodeError:
            pass  # Response might not be JSON

    def deploy_blocklist_changes(self) -> dict:
        """
        Deploy blocklist changes to make them active.
        """
        return self.execute_request("POST", "api/v2/policy/urllist/deploy")

    def execute_request(self, method: str, endpoint: str, **kwargs) -> dict:
        """
        Execute a request to the Netskope API.
        """
        url = self.get_api_url(endpoint)
        headers = {"Authorization": f"Bearer {self.api_key}", **kwargs.get("headers", {})}

        response = requests.request(method, url, headers=headers, **kwargs)

        self._handle_response_error(response)

        return response.json() if response.content else {}
