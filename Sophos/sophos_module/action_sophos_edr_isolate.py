from typing import Any

import requests

from sophos_module.action_base import SophosEDRAction


class ActionSophosEDRIsolateEndpoint(SophosEDRAction):
    def get_endpoint_isolation_status(self, endpoint_id: str) -> Any:
        return self.call_endpoint(
            method="get", url=f"endpoint/v1/endpoints/{endpoint_id}/isolation", use_region_url=True
        )

    def try_to_set_isolation_state(self, endpoint_id: str, enabled: bool, comment: str | None = None) -> Any:
        data: dict[str, Any] = {"enabled": enabled}
        if comment is not None:
            data["comment"] = comment

        return self.call_endpoint(
            method="patch", url=f"endpoint/v1/endpoints/{endpoint_id}/isolation", data=data, use_region_url=True
        )

    def set_isolation_status(self, endpoint_id: str, enabled: bool, comment: str | None = None) -> Any:
        """
        Sophos Endpoint API will return `Bad Request` every time you will
        try to enable/disable already enabled/disabled isolation on an endpoint,
        or whenever there's too little time passed between status changes. So we
        have to make double checks and enrich returned messages
        """
        # check whether endpoint is already in the desired state
        current_status = self.get_endpoint_isolation_status(endpoint_id)
        if current_status["enabled"] == enabled:
            result_label = "enabled" if enabled else "disabled"
            current_status["message"] = "Already %s" % result_label
            return current_status

        try:
            response = self.try_to_set_isolation_state(endpoint_id=endpoint_id, enabled=enabled, comment=comment)
            return response

        except requests.exceptions.HTTPError as err:
            if err.response.status_code == 400:
                # returned as "bad request" in two cases:
                # 1. endpoint is already in the desired state - we checked for that before
                # 2. too little time passed since an isolation state was changed - need to wait
                result = err.response.json()
                result.update(
                    {
                        "error": "Isolation status was changed recently",
                        "message": "We recommend that you wait for a period of time "
                        "between turning endpoint isolation on and off",
                    }
                )
                result.update(current_status)
                return result

    def run(self, arguments: dict[str, Any]) -> Any:
        endpoint_id = arguments["endpoint_id"]
        comment = arguments.get("comment")

        return self.set_isolation_status(endpoint_id=endpoint_id, enabled=True, comment=comment)
