from ..base import BitdefenderAction

class RestoreQuarantineFileAction(BitdefenderAction):
    endpoint_api = "api/v1.0/jsonrpc/quarantine/computers"
    method_name = "createRestoreQuarantineItemTask"

    def run(self, arguments: dict) -> dict:
        response = super().run(arguments)

        return {"result": response.get("result")}