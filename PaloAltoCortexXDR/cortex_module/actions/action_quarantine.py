from typing import Any

from pydantic.main import BaseModel

import sys

sys.path.append(".")

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


from unittest.mock import Mock
from cortex_module.base import CortexModule

cortex_module = CortexModule()
cortex_module.configuration = {
    "api_key": "E3YNwNQrz04feXncLs2AyNXDdOgLkQQF7yJEfGMOfAnaS6anjFjujbL5u2BTLfFjVNgpUczlgU7P7lvE8aPYnWCqMzc8rqGJ5Bjj30VJXqpRJVHts8ng9kpLMyigWZxs",
    "api_key_id": 6,
    "fqdn": "sekoia-integration-xdr.xdr.fa.paloaltonetworks.com",
}

action = QuarantineAction(module=cortex_module)

action.log_exception = Mock()
action.log = Mock()


arguments = QuarantineArguments(
    file_path="C:\\Windows\\system32\\cmd.exe",
    file_hash="249d2eb01764edffe2df2fdfc5c9c783c7d91a5d88b9194f3878562265d4294b",
    endpoint_ids=["0ba7db5bf9d6420e9815e09c9312b175"],
)

action.run(arguments=arguments)
