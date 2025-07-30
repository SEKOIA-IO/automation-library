from ..base import BitdefenderAction

class QuarantineFileAction(BitdefenderAction):
    endpoint_api = "api/v1.0/jsonrpc/quarantine/computers"
    method_name = "createAddFileToQuarantineTask"

    def run(self, arguments: dict) -> dict:
        response = super().run(arguments)

        return {"result": response.get("result")}