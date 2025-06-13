from typing import Any

from pydantic.main import BaseModel

from cortex_module.actions import PaloAltoCortexXDRAction


class QuarantineArguments(BaseModel):
    """
    Arguments for the quarantine action.
    """

    file_path: str
    file_hash: str
    endpoint_ids: list[str] | None = None


class QuarantineAction(PaloAltoCortexXDRAction):
    """
    This action is used to quarantine files on endpoints.
    """

    request_uri = "public_api/v1/endpoints/quarantine"

    def request_payload(self, arguments: dict[str, Any]) -> dict[str, Any]:
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
        model = QuarantineArguments(**arguments)

        endpoint_ids: list[str] = model.endpoint_ids or []

        filters = {"filters": []}
        if endpoint_ids:
            filters["filters"].append(
                {
                    "field": "endpoint_id_list",
                    "operator": "in",
                    "value": endpoint_ids,
                }
            )

        file_hash = {"file_hash": model.file_hash}

        return {
            "request_data": {
                "file_path": model.file_path,
                **file_hash,
                **filters,
            }
        }
