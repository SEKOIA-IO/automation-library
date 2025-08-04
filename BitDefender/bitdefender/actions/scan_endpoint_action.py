from ..base import BitdefenderAction
from ..bitdefender_gravity_zone_api import prepare_scan_endpoint


class ScanEndpointAction(BitdefenderAction):

    def run(self, arguments: dict) -> dict:
        response = self.execute_request(prepare_scan_endpoint(arguments))

        return {"result": response.get("result")}
