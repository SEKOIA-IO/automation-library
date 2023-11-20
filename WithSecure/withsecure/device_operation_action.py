from functools import cached_property
from threading import Event
from typing import Any

from sekoia_automation.action import Action

from withsecure.client import ApiClient
from withsecure.constants import API_DEVICES_OPERATION_URL, API_TIMEOUT


class DeviceOperationAction(Action):
    def run(self, arguments: Any) -> Any:
        raise NotImplementedError()

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

    def _execute_operation_on_device(self, operation_name: str, target: str, parameters: dict | None = None):
        self.log(f"Execute the operation '{operation_name}' on device '{target}'", level="debug")

        request_payload: dict[str, Any] = {"operation": operation_name, "targets": [target]}
        if parameters:
            request_payload["parameters"] = parameters
        headers = {"Accept": "application/json"}
        # create the API client
        client = ApiClient(
            client_id=self.module.configuration.client_id,
            secret=self.module.configuration.secret,
            scope="connect.api.write",
            stop_event=Event(),
            log_cb=self.log,
            default_headers=self._http_default_headers,
        )
        client.post(
            API_DEVICES_OPERATION_URL, timeout=API_TIMEOUT, json=request_payload, headers=headers
        ).raise_for_status()
