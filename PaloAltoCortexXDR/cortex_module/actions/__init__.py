from abc import ABC, abstractmethod
from functools import cached_property
from typing import Any, Generator

from sekoia_automation.action import Action

from cortex_module.base import CortexModule
from cortex_module.client import ApiClient
from cortex_module.helper import format_fqdn


class PaloAltoCortexXDRAction(Action, ABC):
    """
    This is the wrapper over actions for Cortex XDR.
    """

    module: CortexModule

    request_uri: str

    def request_payload(self, arguments: dict[str, Any]) -> dict[str, Any] | Generator[dict[str, Any], None, None]:
        """
        This method is used to build the request payload.

        Args:
            arguments: The arguments passed to the action.
        Returns:
            dict[str, Any]: The request payload.
        """
        raise NotImplementedError("This method should be overridden by the action class.")

    @cached_property
    def client(self) -> ApiClient:
        return ApiClient(
            self.module.configuration.api_key,
            self.module.configuration.api_key_id,
        )

    @cached_property
    def request_url(self) -> str:
        return f"{format_fqdn(self.module.configuration.fqdn)}/{self.request_uri}"

    def handle_error_result(self, result: dict[str, Any]) -> None:
        reply = result.get("reply", {})
        if not isinstance(reply, dict):
            return  # No reply dict to check

        if reply.get("err_code"):
            code = result["reply"]["err_code"]
            error_message = result["reply"].get("err_msg", "Unknown error")
            detailed_message = result["reply"].get("err_extra", "")

            raise ValueError(f"Error in response: {code} - {error_message} {detailed_message}")

    def run(self, arguments: dict[str, Any]) -> dict[str, Any]:
        payload = self.request_payload(arguments)
        response = self.client.post(url=self.request_url, json=payload)

        result: dict[str, Any] = response.json()
        self.handle_error_result(result)

        return result
