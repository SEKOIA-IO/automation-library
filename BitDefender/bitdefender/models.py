from pydantic import BaseModel, ConfigDict

class DetailsModel(BaseModel):
    """Interface for Details"""
    pass

class HashModel(DetailsModel):
    """
    Model for Hash
    """
    algorithm: str
    hash: str

class PathModel(DetailsModel):
    """
    Model for Path
    """
    path: str

class LocalAddressModel(BaseModel):
    """
    Model for Local Address
    """
    any: bool
    ip_mask: str = ""
    port_range: str = ""

class RemoteAddressModel(BaseModel):
    """
    Model for Remote Address
    """
    any: bool
    ip_mask: str = ""
    port_range: str = ""

class DirectlyConnectedModel(BaseModel):
    """
    Model for Directly Connected
    """
    any: bool
    remote_mac: str

class ConnectionModel(DetailsModel):
    """
    Model for Connection
    """
    rule_name: str
    command_line: str = ""
    protocol: str = ""
    direction: str = ""
    ip_version: str = ""
    local_address: LocalAddressModel = {}
    remote_address: RemoteAddressModel = {}
    directly_connected: DirectlyConnectedModel = {}


class RuleModel(BaseModel):
    """
    Model for Rule
    """
    details: DetailsModel

class BlockListModel(BaseModel):
    """
    Model for Block List
    """
    type: str
    rules: list[RuleModel]

# class PushBlockActionRequest(BaseModel):
#     """
#     Request model for PushBlockIocAction
#     """
#     company_id: str
#     block: BlockListModel

class GetBlockListActionRequest(BaseModel):
    """
    Request model for GetBlockListAction
    """
    page: int = 1
    per_page: int = 30

class ItemsModel(BaseModel):
    """
    Model for Items
    """
    type: str
    id: str
    details: DetailsModel

class GetBlockListActionResponse(BaseModel):
    """
    Response model for GetBlockListAction
    """
    total: int
    page: int
    per_page: int
    pages_count: int
    items: list[ItemsModel]

    model_config = ConfigDict(arbitrary_types_allowed=True)

class RemoveBlockActionRequest(BaseModel):
    """
    Request model for RemoveBlockAction
    """
    ids: list[str]