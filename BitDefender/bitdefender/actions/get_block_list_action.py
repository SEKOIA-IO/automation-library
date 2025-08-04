from ..base import BitdefenderAction
from ..models import GetBlockListActionRequest, GetBlockListActionResponse, ItemsModel, HashModel, PathModel, ConnectionModel
from ..bitdefender_gravity_zone_api import prepare_get_block_list_endpoint

class GetBlockListAction(BitdefenderAction):

    def run(self, arguments: GetBlockListActionRequest) -> GetBlockListActionResponse:
        args = arguments.dict(exclude_none=True, by_alias=True)
        response = self.execute_request(
            prepare_get_block_list_endpoint(args)
        )

        items = response['result'].get("items", [])
        itemModels = []
        for item in items:
            type = item.get("type", "")
            response_details = item.get("details", {})
            details = {}
            match type:
                case "hash":
                    details = HashModel(**response_details)
                case "path":
                    details = PathModel(**response_details)
                case "connection":
                    details = ConnectionModel(**response_details)
                case _:
                    continue
            
            itemModel = ItemsModel(
                type=type,
                id=item.get("id", ""),
                details=details
            )
            itemModels.append(itemModel)

        blockList = GetBlockListActionResponse(
            total=response['result'].get("total", 0),
            page=response['result'].get("page", 1),
            per_page=response['result'].get("per_page", 30),
            pages_count=response['result'].get("pages_count", 0),
            items=itemModels
        )       

        return {"result" : blockList.dict(by_alias=True, exclude_none=True)}  # type: ignore