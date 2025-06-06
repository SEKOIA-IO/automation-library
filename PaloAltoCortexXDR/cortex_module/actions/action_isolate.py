from abc import ABC
from typing import Any

from pydantic.main import BaseModel

from cortex_module.actions import PaloAltoCortexXDRAction


class IsolateArguments(BaseModel):
    """
    Arguments for the isolate/unisolate action.
    """

    endpoint_id: str
    incident_id: str | None = None


class BaseIsolateAction(PaloAltoCortexXDRAction, ABC):
    """
    This action is used to isolate.
    """

    def request_payload(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """
        Build the request payload for the action.

        Example of payload:
        {
          "request_data": {
            "endpoint_id": "<value>",
            "incident_id": "<value>"
          }
        }

        Args:
            arguments: The arguments passed to the action.

        Returns:
            dict[str, Any]: The request payload.
        """
        model = IsolateArguments(**arguments)

        result = {
            "request_data": {
                "endpoint_id": model.endpoint_id,
            }
        }

        if model.incident_id:
            result["request_data"]["incident_id"] = model.incident_id

        return result


class IsolateAction(BaseIsolateAction):
    """
    This action is used to isolate.
    """

    request_uri = "public_api/v1/endpoints/isolate"


class UnisolateAction(BaseIsolateAction):
    """
    This action is used to unisolate.
    """

    request_uri = "public_api/v1/endpoints/unisolate"
