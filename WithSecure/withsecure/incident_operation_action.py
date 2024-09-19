from threading import Event
from typing import Any

from sekoia_automation.action import Action

from withsecure.client import ApiClient
from withsecure.constants import API_COMMENT_INCIDENT_URL, API_LIST_DETECTION_URL, API_LIST_INCIDENT_URL, API_TIMEOUT


class IncidentOperationAction(Action):
    def run(self, arguments: Any) -> Any:
        raise NotImplementedError()

    def _execute_operation_on_incident(
        self, operation_name: str, target: str, parameters: dict[str, Any] | None = None
    ) -> Any:
        self.log(f"Execute the operation '{operation_name}' on incident '{target}'", level="debug")

        payload: dict[str, Any] = {"targets": [target]}
        if parameters:
            payload.update(parameters)
        headers = {"Accept": "application/json"}
        # create the API client
        client = ApiClient(
            client_id=self.module.configuration.client_id,
            secret=self.module.configuration.secret,
            scope="connect.api.read connect.api.write",
            stop_event=Event(),
            log_cb=self.log,
        )
        operation_result = []
        if operation_name == "CommentIncident":
            response = client.post(API_COMMENT_INCIDENT_URL, timeout=API_TIMEOUT, json=payload, headers=headers)
            response.raise_for_status()
            operation_result = response.json()

        if operation_name == "UpdateStatusIncident":
            response = client.patch(API_LIST_INCIDENT_URL, timeout=API_TIMEOUT, json=payload, headers=headers)
            response.raise_for_status()
            operation_result = response.json()

        if operation_name == "ListDetectionForIncident":
            params = {"incidentId": target}
            detections = []
            response = client.get(API_LIST_DETECTION_URL, timeout=API_TIMEOUT, params=params, headers=headers)
            response.raise_for_status()
            jsonify_response = response.json()
            detections.extend(jsonify_response.get("items", []))

            # Docs: https://connect.withsecure.com/api-reference/elements#delete-/devices/v1/devices
            while jsonify_response.get("nextAnchor"):
                params["anchor"] = jsonify_response["nextAnchor"]
                response = client.get(API_LIST_DETECTION_URL, timeout=API_TIMEOUT, params=params, headers=headers)
                response.raise_for_status()
                jsonify_response = response.json()
                detections.extend(jsonify_response["items"])

            operation_result = detections

        return operation_result
