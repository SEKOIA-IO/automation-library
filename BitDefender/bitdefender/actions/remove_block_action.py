from ..base import BitdefenderAction
from ..models import RemoveBlockActionRequest
from ..bitdefender_gravity_zone_api import prepare_remove_block_endpoint
class RemoveBlockAction(BitdefenderAction):

    def run(self, arguments: RemoveBlockActionRequest) -> dict:
        args = arguments.dict(exclude_none=True, by_alias=True)
        response = self.execute_request(
            prepare_remove_block_endpoint(args)
        )

        return {"result": response.get("result", False)}