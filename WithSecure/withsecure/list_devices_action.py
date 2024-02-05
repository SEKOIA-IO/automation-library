from threading import Event
from typing import Any

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

    def run(self, arguments: ActionArguments) -> ActionResults:
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

    def build_device_details(self, device: dict[str, Any]) -> Device:
        return Device(id=device["id"], type=device["type"], name=device["name"])
