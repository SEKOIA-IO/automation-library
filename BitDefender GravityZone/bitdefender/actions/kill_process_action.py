from ..base import BitdefenderAction
from ..bitdefender_gravity_zone_api import prepare_kill_process_endpoint


class KillProcessAction(BitdefenderAction):

    def run(self, arguments: dict) -> dict:
        response = self.execute_request(prepare_kill_process_endpoint(arguments))

        return {"result": response.get("result", False)}
