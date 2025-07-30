from ..base import BitdefenderAction

class CustomScanEndpointAction(BitdefenderAction):
    endpoint_api = "api/v1.0/jsonrpc/network"
    method_name = "createScanTask"

    def run(self, arguments: dict) -> dict:
        response = super().run(arguments)

        return {"result": response.get("result")}