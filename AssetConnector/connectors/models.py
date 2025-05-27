from pydantic import BaseModel

# from enum import Enum
from typing import Literal


class DefaultAssetConnectorConfiguration(BaseModel):
    sekoia_base_url: str | None
    api_key: str
    frequency: int = 60


# class AssetType(Enum):
#     HOST_TYPE = "host"
#     ACCOUNT_TYPE = "account"


class AssetObject(BaseModel):
    name: str
    type: Literal["account", "host"]


class AssetList(BaseModel):
    assets: list[AssetObject] = []
