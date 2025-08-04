from ..base import BitdefenderAction
from ..bitdefender_gravity_zone_api import prepare_restore_quarantine_file_endpoint
class RestoreQuarantineFileAction(BitdefenderAction):

    def run(self, arguments: dict) -> dict:
        response = self.execute_request(
            prepare_restore_quarantine_file_endpoint(arguments)
        )

        return {"result": response.get("result")}