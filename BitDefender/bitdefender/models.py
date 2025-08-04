from pydantic.v1 import BaseModel, Field

class DetailsModel(BaseModel):
    """Interface for Details"""
    pass

class HashModel(DetailsModel):
    """
    Model for Hash
    """
    algorithm: str
    hash: str
    class Config:
        allow_population_by_field_name = True

class PathModel(DetailsModel):
    """
    Model for Path
    """
    path: str

class LocalAddressModel(BaseModel):
    """
    Model for Local Address
    """
    any: bool | None = Field(None, alias="any")
    ip_mask: str | None = Field(None, alias="ipMask")
    port_range: str | None = Field(None, alias="portRange")

    class Config:
        allow_population_by_field_name = True

class RemoteAddressModel(BaseModel):
    """
    Model for Remote Address
    """
    any: bool | None = Field(None, alias="any")
    ip_mask: str | None = Field(None, alias="ipMask")
    port_range: str | None = Field(None, alias="portRange")

    class Config:
        allow_population_by_field_name = True

class DirectlyConnectedModel(BaseModel):
    """
    Model for Directly Connected
    """
    enable: bool | None = Field(None, alias="enable")
    remote_mac: str | None = Field(None, alias="remoteMac")

class ConnectionModel(DetailsModel):
    """
    Model for Connection
    """
    rule_name: str = Field("", alias="ruleName")
    command_line: str | None = Field(None, alias="commandLine")
    protocol: str | None = None
    direction: str | None = None
    ip_version: str | None = Field(None, alias="ipVersion")
    local_address: LocalAddressModel | None = Field(None, alias="localAddress")
    remote_address: RemoteAddressModel | None = Field(None, alias="remoteAddress")
    directly_connected: DirectlyConnectedModel | None = Field(None, alias="directlyConnected")
    class Config:
        allow_population_by_field_name = True


class RuleModel(BaseModel):
    """
    Model for Rule
    """
    details: DetailsModel
    class Config:
        allow_population_by_field_name = True

class BlockListModel(BaseModel):
    """
    Model for Block List
    """
    type: str
    rules: list[RuleModel]
    class Config:
        allow_population_by_field_name = True

class GetBlockListActionRequest(BaseModel):
    """
    Request model for GetBlockListAction
    """
    page: int = 1
    per_page: int = Field(30, alias="perPage")

    class Config:
        allow_population_by_field_name = True

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
    per_page: int = Field(..., alias="perPage")
    pages_count: int = Field(..., alias="pagesCount")
    items: list[ItemsModel]

    class Config:
        allow_population_by_field_name = True

class RemoveBlockActionRequest(BaseModel):
    """
    Request model for RemoveBlockAction
    """
    ids: list[str]