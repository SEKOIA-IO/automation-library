from posixpath import join as urljoin
from typing import Annotated, Any, Optional
from uuid import UUID

import requests
from pydantic import BaseModel, Field, StringConstraints
from sekoia_automation.action import Action

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class UpdateAssetArguments(BaseModel):
    uuid: UUID = Field(..., description="The identifier of the asset")
    entity_uuid: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    type: Optional[str] = None
    category: Optional[str] = None
    criticality: Optional[int] = None
    props: Optional[dict] = None
    atoms: Optional[dict] = None
    tags: Optional[list] = None
    revoked: Optional[bool] = None
    reviewed: Optional[bool] = None


class UpdateAsset(Action):
    ALLOWED_FIELDS = [
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

        payload = {field: getattr(arguments, field) for field in self.ALLOWED_FIELDS if getattr(arguments, field)}

        if arguments.revoked is not None:
            payload["revoked"] = arguments.revoked

        if arguments.reviewed is not None:
            payload["reviewed"] = arguments.reviewed

        return self.perform_request(asset_uuid=asset_uuid, payload=payload)
