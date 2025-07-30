from ..base import BitdefenderAction
from ..models import RemoveBlockActionRequest

class RemoveBlockAction(BitdefenderAction):
    endpoint_api = "api/v1.2/jsonrpc/incidents"
    method_name = "removeFromBlocklist"

    def run(self, arguments: RemoveBlockActionRequest) -> dict:
        response = super().run(arguments)

        return {"result": response.get("result", False)}