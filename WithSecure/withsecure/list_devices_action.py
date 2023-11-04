from functools import cached_property
from threading import Event

from pydantic import BaseModel
from sekoia_automation.action import Action

from withsecure.client import ApiClient
from withsecure.constants import API_LIST_DEVICES_URL, API_TIMEOUT


class ActionArguments(BaseModel):
    organization_id: str | None = None


class Device(BaseModel):
    id: str
    type: str
    name: str


class ActionResults(BaseModel):
    devices: list[Device] = []


class ListDevicesAction(Action):
    results_model = ActionResults

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

    def run(self, arguments: ActionArguments):
        # set request params
        params = {}
        if arguments.organization_id:
            params["organizationId"] = arguments.organization_id

        headers = {"Accept": "application/json"}

        # create the API client
        client = ApiClient(
            client_id=self.module.configuration.client_id,
            secret=self.module.configuration.secret,
            scope="connect.api.read",
            stop_event=Event(),
            log_cb=self.log,
            default_headers=self._http_default_headers,
        )

        devices: list[Device] = []

        response = client.get(API_LIST_DEVICES_URL, timeout=API_TIMEOUT, params=params, headers=headers)
        response.raise_for_status()
        payload = response.json()
        for device in payload["items"]:
            devices.append(self.build_device_details(device))

        while payload.get("nextAnchor"):
            params["anchor"] = payload["nextAnchor"]
            response = client.get(API_LIST_DEVICES_URL, timeout=API_TIMEOUT, params=params, headers=headers)
            response.raise_for_status()
            payload = response.json()

            for device in payload["items"]:
                devices.append(self.build_device_details(device))

        return ActionResults(devices=devices)

    def build_device_details(self, device):
        return Device(id=device["id"], type=device["type"], name=device["name"])
