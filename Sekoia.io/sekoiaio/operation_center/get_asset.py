from posixpath import join as urljoin

from sekoia_automation.action import Action
import requests
from datetime import datetime


ASSETV2_TYPE_TO_V1_TYPE = {
    "host": {"uuid": "65f8ebba-e400-4ef7-844d-2881e2cf175c", "name": "computer"},
    "network": {"uuid": "4aac4b72-14cf-4159-a4e5-32fa8c1f3da6", "name": "network"},
    "account": {"uuid": "e47dcc10-7c1d-4922-b20f-5d16b5e3648f", "name": "person"},
}

ASSETV2_TYPE_TO_V1_CATEGORY = {
    "host": {"uuid": "1c646cb3-54c3-44cb-88d3-2db24de2fcf4", "name": "technical"},
    "network": {"uuid": "1c646cb3-54c3-44cb-88d3-2db24de2fcf4", "name": "technical"},
    "account": {"uuid": "87da56fc-1e88-467a-9e62-940caad7d318", "name": "people"},
}

ASSETV2_ATOM_OR_PROP_TO_V1_KEY = {
    "ipv4": {"uuid": "1aa12ae4-c22e-4d2e-89cb-764285b74fef", "name": "ip-v4"},
    "ipv6": {"uuid": "6481e9df-b03c-403a-8dc8-30aa42986a04", "name": "ip-v6"},
    "cidrv4": {"uuid": "e2440ef6-02af-4da0-ac7a-511821033d74", "name": "cidr-v4"},
    "cidrv6": {"uuid": "a954fbf8-d79f-40e0-84a6-cefbfa998696", "name": "cidr-v6"},
    "asn": {"uuid": "7a39c0cf-e470-4a06-afba-da2009fdc7d1", "name": "as"},
    "hostname": {"uuid": "93e78f59-ce78-4349-a4d9-168fe76dffb5", "name": "host"},
    "fqdn": {"uuid": "abb98318-4bf9-4731-9455-28a736a88ac2", "name": "fqdn"},
    "lastname": {"uuid": "d54da6bd-ed4f-47f4-b49b-f2f3abdb4580", "name": "lastname"},
    "username": {"uuid": "d4ad816e-6c6f-4c96-b366-4939e67e20b6", "name": "name"},
}


class GetAsset(Action):

    def url(self, path: str) -> str:
        return urljoin(self.module.configuration["base_url"], "api/v2/asset-management/assets/", path)

    @property
    def headers(self) -> dict:
        api_key = self.module.configuration["api_key"]
        return {"Authorization": f"Bearer {api_key}"}

    def perform_request(self, asset_uuid):

        result = requests.get(self.url(asset_uuid), headers=self.headers)

        if not result.ok:
            self.error(f"Could not fetch asset {asset_uuid}, status code: {result.status_code}")
            return None
        return result.json()

    def serialize_asset_criticity(self, criticity: int):
        display_str = "medium"
        if criticity < 34:
            display_str = "low"
        elif criticity >= 68:
            display_str = "high"
        return {"value": criticity, "display": display_str}

    def transform_asset(self, asset):
        if asset is None:
            return None
        if isinstance(asset["created_at"], str):
            asset["created_at"] = datetime.fromisoformat(asset["created_at"])
        if isinstance(asset["updated_at"], str):
            asset["updated_at"] = datetime.fromisoformat(asset["updated_at"])

        return {
            "uuid": asset["uuid"],
            "name": asset["name"],
            "category": ASSETV2_TYPE_TO_V1_CATEGORY.get(asset["type"]),
            "description": asset["description"],
            "criticity": self.serialize_asset_criticity(asset["criticality"]),
            "asset_type": ASSETV2_TYPE_TO_V1_TYPE.get(asset["type"]),
            "community_uuid": asset["community_uuid"],
            "owners": [],
            "created_at": asset["created_at"],
            "updated_at": asset["updated_at"],
            "keys": [
                {
                    **ASSETV2_ATOM_OR_PROP_TO_V1_KEY.get(key, {"name": key if key != "custom" else v.split("=")[0]}),
                    "value": v if key != "custom" else v.split("=")[-1],
                }
                for key, values in asset.get("atoms", {}).items()
                for v in (values if isinstance(values, list) else [values])
            ],
            "attributes": [
                {**ASSETV2_ATOM_OR_PROP_TO_V1_KEY.get(key, {"name": key}), "value": v}
                for key, values in asset.get("props", {}).items()
                for v in (values if isinstance(values, list) else [values])
            ],
        }

    def run(self, arguments: dict):

        asset_uuid = arguments.get("uuid")
        return self.transform_asset(self.perform_request(asset_uuid))
