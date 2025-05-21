from abc import ABC
from typing import Any

from pydantic.main import BaseModel

from cortex_module.actions import ArgumentsT, PaloAltoCortexXDRAction


class IsolateArguments(BaseModel):
    """
    Arguments for the isolate/unisolate action.
    """

    endpoint_id: str
    incident_id: str | None = None


class BaseIsolateAction(PaloAltoCortexXDRAction[IsolateArguments], ABC):
    """
    This action is used to isolate.
    """

    def request_payload(self, arguments: IsolateArguments) -> dict[str, Any]:
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
        result = {
            "request_data": {
                "endpoint_id": arguments.endpoint_id,
            }
        }

        if arguments.incident_id:
            result["request_data"]["incident_id"] = arguments.incident_id

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
