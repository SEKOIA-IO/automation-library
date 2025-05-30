from typing import Any

from pydantic.main import BaseModel

from cortex_module.actions import PaloAltoCortexXDRAction


class CommentAlertArguments(BaseModel):
    """
    Arguments for the update alert action.
    """

    alert_id_list: list[str]
    comment: str


class CommentAlertAction(PaloAltoCortexXDRAction[CommentAlertArguments]):
    """
    This action is used to comment alert.
    """

    request_uri = "public_api/v1/alerts/update_alerts"

    def request_payload(self, arguments: CommentAlertArguments) -> dict[str, Any]:
        """
        Build the request payload for the action.

        Example of payload:
        {
          "request_data": {
            "alert_id_list": [
              "<list of alert IDs>"
            ],
            "update_data": {
              "comment": "<str>"
            }
          }
        }

        Args:
            arguments: The arguments passed to the action.

        Returns:
            dict[str, Any]: The request payload.
        """
        return {
            "request_data": {"alert_id_list": arguments.alert_id_list, "update_data": {"comment": arguments.comment}}
        }
