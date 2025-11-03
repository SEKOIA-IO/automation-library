from typing import Any

from cortex_module.actions import PaloAltoCortexXDRAction


class ListEndpointsAction(PaloAltoCortexXDRAction):
    """
    This action is used to list endpoints
    """

    request_uri = "public_api/v1/endpoints/get_endpoints"

    def request_payload(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return {}
