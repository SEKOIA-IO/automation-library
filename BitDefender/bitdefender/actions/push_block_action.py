from ..base import BitdefenderAction
from ..models import BlockListModel
from ..bitdefender_gravity_zone_api import prepare_push_block_endpoint

class PushBlockAction(BitdefenderAction):
    
    def run(self, arguments: BlockListModel) -> dict:
        args = arguments.dict(exclude_none=True, by_alias=True)
        response = self.execute_request(
            prepare_push_block_endpoint(args)
        )

        return {"result": response.get("result", False)}