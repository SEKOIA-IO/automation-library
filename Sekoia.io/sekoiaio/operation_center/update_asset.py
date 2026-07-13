from posixpath import join as urljoin
from typing import Any, ClassVar, Literal
from uuid import UUID

import requests
from pydantic import BaseModel, Field
from sekoia_automation.action import Action

AssetType = Literal["host", "account", "network"]
AtomScalar = str | int | float | bool | None
AtomsDict = dict[str, list[AtomScalar] | AtomScalar]


class UpdateAssetArguments(BaseModel):
    uuid: UUID = Field(..., description="The identifier of the asset")
    entity_uuid: UUID | None = None
    name: str | None = Field(None, min_length=2)
    description: str | None = None
    type: AssetType | None = None
    category: str | None = None
    criticality: int | None = Field(None, ge=0, le=100)
    props: dict | None = None
    atoms: AtomsDict | None = None
    tags: list[str] | None = None
    revoked: bool | None = None
    reviewed: bool | None = None


class UpdateAsset(Action):
    ALLOWED_FIELDS: ClassVar[list[str]] = [
        "entity_uuid",
        "name",
        "description",
        "type",
        "category",
        "criticality",
        "props",
        "atoms",
        "tags",
    ]

    def url(self, path: str) -> str:
        return urljoin(self.module.configuration["base_url"], "api/v2/asset-management/assets/", path)

    @property
    def headers(self) -> dict:
        api_key = self.module.configuration["api_key"]
        return {"Authorization": f"Bearer {api_key}"}

    def perform_request(self, asset_uuid: UUID, payload: dict) -> Any:
        asset_uuid_str = str(asset_uuid)
        result = requests.put(self.url(asset_uuid_str), headers=self.headers, json=payload, timeout=60)

        if not result.ok:
            self.error(f"Could not fetch asset {asset_uuid_str}, status code: {result.status_code}")
            return None

        return result.json()

    def run(self, arguments: UpdateAssetArguments) -> Any:
        asset_uuid = arguments.uuid

        payload = {}
        for field in self.ALLOWED_FIELDS:
            value = getattr(arguments, field)
            if not value:
                continue
            if field == "entity_uuid":
                value = str(value)
            payload[field] = value

        if arguments.revoked is not None:
            payload["revoked"] = arguments.revoked

        if arguments.reviewed is not None:
            payload["reviewed"] = arguments.reviewed

        return self.perform_request(asset_uuid=asset_uuid, payload=payload)
