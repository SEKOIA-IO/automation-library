from ..base import BitdefenderAction
from ..models import GetBlockListActionRequest, GetBlockListActionResponse, ItemsModel, HashModel, PathModel, RemoteAddressModel, LocalAddressModel, DirectlyConnectedModel, ConnectionModel

class GetBlockListAction(BitdefenderAction):
    endpoint_api = "api/v1.2/jsonrpc/incidents"
    method_name = "getBlocklistItems"

    def run(self, arguments: GetBlockListActionRequest) -> GetBlockListActionResponse:
        response = super().run(arguments)

        items = response.get("items", [])
        itemModels = list[ItemsModel]
        for item in items:
            type = item.get("type", "")
            response_details = item.get("details", {})
            details = {}
            match type:
                case "hash":
                    details = HashModel(
                        hash=response_details.get("hash", ""),
                        algorithm=response_details.get("algorithm", "")
                    )
                case "path":
                    details = PathModel(
                        path=response_details.get("path", "")
                    )
                case "connection":
                    remote_address = RemoteAddressModel(
                        any=response_details.get("remoteAddress", {}).get("any", False),
                        ip_mask=response_details.get("remoteAddress", {}).get("ipMask", ""),
                        port_range=response_details.get("remoteAddress", {}).get("portRange", "")
                    )
                    local_address = LocalAddressModel(
                        any=response_details.get("localAddress", {}).get("any", False),
                        ip_mask=response_details.get("localAddress", {}).get("ipMask", ""),
                        port_range=response_details.get("localAddress", {}).get("portRange", "")
                    )
                    directly_connected = DirectlyConnectedModel(
                        any=response_details.get("directlyConnected", {}).get("any", False),
                        remote_mac=response_details.get("directlyConnected", {}).get("remoteMac", "")
                    )
                    details = ConnectionModel(
                        rule_name=response_details.get("ruleName", ""),
                        command_line=response_details.get("commandLine", ""),
                        protocol=response_details.get("protocol", ""),
                        direction=response_details.get("direction", ""),
                        ip_version=response_details.get("ipVersion", ""),
                        local_address=local_address,
                        remote_address=remote_address,
                        directly_connected=directly_connected
                    )
                case _:
                    continue
            
            itemModel = ItemsModel(
                type=type,
                id=item.get("id", ""),
                details=details
            )
            itemModels.append(itemModel)

        blockList = GetBlockListActionResponse()
        blockList.total = response.get("total", 0)
        blockList.page = response.get("page", 1)
        blockList.per_page = response.get("perPage", 30)
        blockList.pages_count = response.get("pagesCount", 0)
        blockList.items = itemModels
        

        return blockList