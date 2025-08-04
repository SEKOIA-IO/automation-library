from ..base import BitdefenderAction
from ..bitdefender_gravity_zone_api import prepare_isolate_endpoint


class IsolateEndpointAction(BitdefenderAction):

    def run(self, arguments: dict) -> dict:

        response = self.execute_request(prepare_isolate_endpoint(arguments))

        return {"result": response.get("result", False)}
