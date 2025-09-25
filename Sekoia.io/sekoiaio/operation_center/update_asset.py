from posixpath import join as urljoin
from typing import Any

import requests
from sekoia_automation.action import Action


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

    def perform_request(self, asset_uuid: str, payload: dict) -> Any:
        result = requests.put(self.url(asset_uuid), headers=self.headers, json=payload, timeout=60)

        if not result.ok:
            self.error(f"Could not fetch asset {asset_uuid}, status code: {result.status_code}")
            return None

        return result.json()

    def run(self, arguments: Any) -> Any:
        asset_uuid = arguments["uuid"]

        payload = {k: arguments[k] for k in self.ALLOWED_FIELDS if arguments.get(k)}

        revoked = arguments.get("revoked")
        if revoked is not None:
            payload["revoked"] = revoked

        reviewed = arguments.get("reviewed")
        if reviewed is not None:
            payload["reviewed"] = reviewed

        return self.perform_request(asset_uuid=asset_uuid, payload=payload)
