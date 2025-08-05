from ..base import BitdefenderAction
from ..models import BlockListModel
from ..bitdefender_gravity_zone_api import prepare_push_block_endpoint
from ..helpers import parse_push_block


class PushBlockAction(BitdefenderAction):

    def run(self, arguments: dict) -> dict:
        parsed_args: BlockListModel = parse_push_block(arguments)
        args = parsed_args.dict(exclude_none=True, by_alias=True)
        response = self.execute_request(prepare_push_block_endpoint(args))

        return {"result": response.get("result", False)}
