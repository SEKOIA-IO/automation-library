from threading import Event
from typing import Any

from sekoia_automation.action import Action

from withsecure.client import ApiClient
from withsecure.constants import API_RESPONSE_ACTIONS_URL, API_TIMEOUT
from withsecure.logging import get_logger

logger = get_logger()


class ResponseAction(Action):
    def run(self, arguments: Any) -> Any:
        raise NotImplementedError()

    def _execute_operation_on_device(
        self, action_type: str, target: str, organization_id: str, parameters: dict[str, Any] | None = None
    ) -> Any:
        self.log(
            f"Execute the action type '{action_type}' on device '{target}'",
            level="debug",
        )

        request_payload: dict[str, Any] = {
            "type": action_type,
            "organizationId": organization_id,
            "targets": [target],
            "parameters": {},
        }
        if parameters:
            # add only parameters with values
            params_with_values = {k: v for k, v in parameters.items() if v is not None}
            if len(params_with_values) > 0:
                request_payload["parameters"] = params_with_values

        headers = {"Accept": "application/json"}
        # create the API client
        client = ApiClient(
            client_id=self.module.configuration.client_id,
            secret=self.module.configuration.secret,
            scope="connect.api.read connect.api.write",
            stop_event=Event(),
            log_cb=self.log,
        )
        response = client.post(
            API_RESPONSE_ACTIONS_URL,
            timeout=API_TIMEOUT,
            json=request_payload,
            headers=headers,
        )

        if not response.ok:
            response_json = response.json()
            logger.error(
                response_json["message"],
                code=response_json["code"],
                transaction_id=response_json["transactionId"],
            )

        response.raise_for_status()

        return response.json()
