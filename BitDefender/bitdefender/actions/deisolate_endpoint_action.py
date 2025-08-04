from ..base import BitdefenderAction
from ..bitdefender_gravity_zone_api import prepare_deisolate_endpoint


class DeisolateEndpointAction(BitdefenderAction):

    def run(self, arguments: dict) -> dict:
        response = self.execute_request(prepare_deisolate_endpoint(arguments))
        return {"result": response.get("result", False)}
