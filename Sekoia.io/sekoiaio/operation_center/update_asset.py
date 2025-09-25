from posixpath import join as urljoin
from typing import Any

import requests
from sekoia_automation.action import Action


class UpdateAsset(Action):
    def url(self, path: str) -> str:
        return urljoin(self.module.configuration["base_url"], "api/v2/asset-management/assets/", path)

    @property
    def headers(self) -> dict:
        api_key = self.module.configuration["api_key"]
        return {"Authorization": f"Bearer {api_key}"}

    def perform_request(self, asset_uuid: str, payload: dict) -> Any:
        result = requests.put(self.url(asset_uuid), headers=self.headers, json=payload)

        if not result.ok:
            self.error(f"Could not fetch asset {asset_uuid}, status code: {result.status_code}")
            return None

        return result.json()

    def run(self, arguments: Any) -> Any:
        asset_uuid = arguments["uuid"]

        payload = {}
        entity_uuid = arguments.get("entity_uuid")
        if entity_uuid:
            payload["entity_uuid"] = entity_uuid

        name = arguments.get("name")
        if name:
            payload["name"] = name

        description = arguments.get("description")
        if description:
            payload["description"] = description

        asset_type = arguments.get("type")
        if asset_type:
            payload["type"] = asset_type

        category = arguments.get("category")
        if category:
            payload["category"] = category

        criticality = arguments.get("criticality")
        if criticality:
            payload["criticality"] = criticality

        props = arguments.get("props")
        if props:
            payload["props"] = props

        atoms = arguments.get("atoms")
        if atoms:
            payload["atoms"] = atoms

        tags = arguments.get("tags")
        if tags:
            payload["tags"] = tags

        revoked = arguments.get("revoked")
        if revoked:
            payload["revoked"] = revoked

        reviewed = arguments.get("reviewed")
        if reviewed:
            payload["reviewed"] = reviewed

        response = self.perform_request(asset_uuid=asset_uuid, payload=payload)

        return response
