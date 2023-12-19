from threading import Event
from typing import Any

from sekoia_automation.action import Action

from withsecure.client import ApiClient
from withsecure.constants import API_LIST_DETECTION_URL, API_COMMENT_INCIDENT_URL, API_LIST_INCIDENT_URL, API_TIMEOUT


class IncidentOperationAction(Action):
    def run(self, arguments: Any) -> Any:
        raise NotImplementedError()

    def _execute_operation_on_incident(self, operation_name: str, target: str, parameters: dict | None = None):
        self.log(f"Execute the operation '{operation_name}' on incident '{target}'", level="debug")

        params: dict[str, Any] = {"targets": [target]}
        if parameters:
            params.update(parameters)
        headers = {"Accept": "application/json"}
        # create the API client
        client = ApiClient(
            client_id=self.module.configuration.client_id,
            secret=self.module.configuration.secret,
            scope="connect.api.write",
            stop_event=Event(),
            log_cb=self.log,
        )
        if operation_name == "CommentIncident":
            client.post(
                API_COMMENT_INCIDENT_URL, timeout=API_TIMEOUT, params=params, headers=headers
            ).raise_for_status()
        if operation_name == "UpdateStatusIncident":
            client.patch(API_LIST_INCIDENT_URL, timeout=API_TIMEOUT, params=params, headers=headers).raise_for_status()
        if operation_name == "ListDetectionForIncident":
            params = {"incidentId": target}
            client.get(API_LIST_DETECTION_URL, timeout=API_TIMEOUT, params=params, headers=headers).raise_for_status()
