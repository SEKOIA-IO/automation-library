from typing import Any

from pydantic.main import BaseModel

from cortex_module.actions import ArgumentsT, PaloAltoCortexXDRAction


class QuarantineArguments(BaseModel):
    """
    Arguments for the quarantine action.
    """

    file_path: str
    file_hash: str | None = None
    endpoint_ids: list[str] | None = None


class QuarantineAction(PaloAltoCortexXDRAction[QuarantineArguments]):
    """
    This action is used to quarantine files on endpoints.
    """

    request_uri = "public_api/v1/endpoints/quarantine"

    def request_payload(self, arguments: QuarantineArguments) -> dict[str, Any]:
        """
        Build the request payload for the quarantine action.

        Example of payload:
        {
          "request_data": {
            "filters": [
              {
                "field": "endpoint_id_list",
                "operator": "in",
                "value": [
                  "<endpoint ID>"
                ]
              }
            ],
            "file_path": "C:\\<file path>\\test_x64.msi",
            "file_hash": "<hash value>"
          }
        }

        Args:
            arguments: The arguments passed to the action.

        Returns:
            dict[str, Any]: The request payload.
        """
        endpoint_ids = arguments.endpoint_ids or []

        filters = {}
        if endpoint_ids:
            filters = {"filters": {"field": "endpoint_id_list", "operator": "in", "value": endpoint_ids}}

        file_hash = {"file_hash": arguments.file_hash} if arguments.file_hash else {}

        return {
            "request_data": {
                "file_path": arguments.file_path,
                **file_hash,
                **filters,
            }
        }
