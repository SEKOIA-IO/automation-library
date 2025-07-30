from ..base import BitdefenderAction
from ..models import BlockListModel

class PushBlockAction(BitdefenderAction):
    endpoint_api = "api/v1.2/jsonrpc/incidents"
    method_name = "addToBlocklist"

    def run(self, arguments: BlockListModel) -> dict:
        response = super().run(arguments)

        return {"result": response.get("result", False)}