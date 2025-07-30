from ..base import BitdefenderAction

class IsolateEndpointAction(BitdefenderAction):
    endpoint_api = "api/v1.0/jsonrpc/incidents"
    method_name = "createIsolateEndpointTask"

    def run(self, arguments: dict) -> dict:
        response = super().run(arguments)

        return {"result": response.get("result", False)}