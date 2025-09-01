from functools import cached_property
import json

from sekoia_automation.action import Action
from bitdefender.client import ApiClient
from requests import Response

from .logging import get_logger
from .helpers import handle_uri

logger = get_logger()


class BitdefenderAction(Action):

    @cached_property
    def api_key(self):
        return self.module.configuration["api_key"]

    @cached_property
    def api_url(self):
        return handle_uri(self.module.configuration["url"])

    @cached_property
    def client(self):
        return ApiClient(
            instance_url=self.module.configuration["url"],
            api_key=self.module.configuration["api_key"],
            nb_retries=5,
            ratelimit_per_second=5,
        )

    def get_api_url(self, endpoint_api) -> str:
        return f"{self.api_url}/{endpoint_api}"

    def _handle_response_error(self, response: Response) -> None:
        if not response.ok:
            logger.error(
                "Failed request to Bitdefender API",
                status_code=response.status_code,
                reason=response.reason,
                error=response.content,
            )

            message = f"Request to Bitdefender API failed with status {response.status_code} - {response.reason}"
            self.log(message=message, level="error")
            response.raise_for_status()

        json_body = json.loads(response.text)

        if "error" in json_body:
            error_message = json_body["error"].get("message", "Unknown error")
            error_data = json_body["error"].get("data", {})
            if error_data:
                error_message += f" - {error_data}"
            logger.error(
                "Bitdefender API returned an error",
                error=error_message,
                status_code=response.status_code,
            )
            raise ValueError(f"Bitdefender API returned an error: {error_message}")

    def execute_request(self, arguments: dict) -> dict:
        """
        Execute the request to the Bitdefender API.
        """
        if not arguments["api"] or not arguments["body"]:
            raise ValueError("Endpoint API and body must be defined.")

        url = self.get_api_url(arguments["api"])
        response = self.client.post(url, json=arguments["body"])

        self._handle_response_error(response)

        return response.json()
