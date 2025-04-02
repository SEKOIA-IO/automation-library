from urllib.parse import urljoin
from typing import List, Dict, Any, Optional
import requests
import json
from pydantic.v1 import BaseModel
from sekoia_automation.action import Action


class Arguments(BaseModel):
    user_ad_data: Optional[Dict[str, Any]] = None
    asset_synchronization_configuration: Dict[str, Any]
    community_uuid: str
    user_ad_file: Optional[str] = None


class SynchronizeAssetsWithAD(Action):
    """
    Action to synchronize asset with Active Directory (AD).
    """

    def run(self, arguments: dict) -> Dict[str, List[Dict[str, Any]]]:
        asset_conf = arguments["asset_synchronization_configuration"]
        community_uuid = arguments["community_uuid"]
        user_ad_data = self.json_argument("user_ad_data", arguments)

        # Normalize user_ad_data to a list for uniform processing
        if not isinstance(user_ad_data, list):
            user_ad_data = [user_ad_data]

        # Extract and validate configuration
        base_url = self.module.configuration.get("base_url", "").rstrip("/")
        api_key = self.module.configuration.get("api_key", "")
        if not base_url or not api_key:
            self.error("Configuration must include 'base_url' and 'api_key'.")

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }

        asset_name_field = asset_conf.get("asset_name_field")
        if not asset_name_field:
            self.error("Configuration must include 'asset_name_field'.")

        assert isinstance(asset_name_field, str)

        session = requests.Session()
        session.headers.update(headers)

        def get_assets(search_query: str, also_search_in_detection_properties: bool = False) -> Dict[str, Any]:
            params = {"search": search_query}
            if also_search_in_detection_properties:
                params["also_search_in_detection_properties"] = "true"
            api_path = urljoin(base_url + "/", "v2/asset-management/assets")
            response = session.get(api_path, params=params)
            if not response.ok:
                self.error(f"HTTP GET request failed: {response.url} with status code {response.status_code}")
            return response.json()

        def post_request(endpoint: str, json_data: str) -> Dict[str, Any]:
            api_path = urljoin(base_url + "/", endpoint)
            response = session.post(api_path, data=json_data)
            if not response.ok:
                self.error(f"HTTP POST request failed: {api_path} with status code {response.status_code}")
            return response.json()

        def put_request(endpoint: str, json_data: str) -> None:
            api_path = urljoin(base_url + "/", endpoint)
            response = session.put(api_path, data=json_data)
            if not response.ok:
                self.error(f"HTTP PUT request failed: {api_path} with status code {response.status_code}")

        def merge_assets(destination: str, sources: List[str]) -> None:
            api_path = urljoin(base_url + "/", "v2/asset-management/assets/merge")
            payload = {"destination": destination, "sources": sources}
            response = session.post(api_path, json=payload)
            if not response.ok:
                self.error(f"HTTP POST merge request failed: {api_path} with status code {response.status_code}")

        responses = []  # To collect responses for each user_ad_data item

        for index, single_user_ad_data in enumerate(user_ad_data, start=1):
            self.log(f"Processing user_ad_data item {index}/{len(user_ad_data)}")

            asset_name = single_user_ad_data.get(asset_name_field)
            if not asset_name:
                self.error(f"User AD data does not contain the asset_name_field: '{asset_name_field}'.")

            assert isinstance(asset_name, str)

            # Search for asset by name
            asset_name_json = get_assets(search_query=asset_name)

            # Search assets with detection properties
            detection_properties_config = asset_conf.get("detection_properties", {})
            found_assets = set()

            for prop, keys in detection_properties_config.items():
                for key in keys:
                    value = single_user_ad_data.get(key)
                    if value:
                        assets = get_assets(search_query=value, also_search_in_detection_properties=True)
                        if assets.get("total", 0) > 0:
                            for asset in assets.get("items", []):
                                found_assets.add(asset["uuid"])

            # Build asset payload
            detection_properties = {}
            for prop, keys in detection_properties_config.items():
                values = [
                    single_user_ad_data[key] for key in keys if key in single_user_ad_data and single_user_ad_data[key]
                ]
                if values:
                    detection_properties[prop] = values

            contextual_properties_config = asset_conf.get("contextual_properties", {})
            custom_properties = {}
            for prop, ad_field in contextual_properties_config.items():
                value = single_user_ad_data.get(ad_field)
                if value is not None:
                    custom_properties[prop] = value

            payload_asset = {
                "name": asset_name,
                "description": "",
                "type": "account",
                "category": "user",
                "reviewed": True,
                "source": "manual",
                "props": custom_properties,
                "atoms": detection_properties,
            }
            json_payload_asset = json.dumps(payload_asset)

            created_asset = False
            destination_asset = ""

            if asset_name_json.get("total", 0) == 1:
                self.log(f"Asset name search response: {asset_name_json} and payload asset is {json_payload_asset}")
                asset_record = asset_name_json["items"][0]
                if asset_record.get("name") and str(asset_record["name"]).lower() == asset_name.lower():
                    asset_uuid = asset_record["uuid"]
                    destination_asset = asset_uuid
                    created_asset = False

                    # Ensure asset_uuid is in found_assets
                    found_assets.add(asset_uuid)

                    # Remove destination_asset from sources to merge
                    sources_to_merge = list(found_assets - {destination_asset})

                    if sources_to_merge:
                        merge_assets(destination=destination_asset, sources=sources_to_merge)

                    endpoint = f"v2/asset-management/assets/{destination_asset}"
                    self.log(f"PUT request: {endpoint} and payload asset is {json_payload_asset}")
                    put_request(endpoint=endpoint, json_data=json_payload_asset)
                else:
                    self.error(f"Unexpected asset name search response: {asset_name_json}")
            elif asset_name_json.get("total", 0) == 0:
                # Asset does not exist, create it
                created_asset = True

                # Create the asset
                payload_asset["community_uuid"] = community_uuid
                create_response = post_request(
                    endpoint="v2/asset-management/assets", json_data=json.dumps(payload_asset)
                )
                destination_asset = create_response.get("uuid", None)
                if destination_asset is None:
                    self.error("Asset creation response does not contain 'uuid'.")

                # Merge found assets into the new asset
                sources_to_merge = list(found_assets)
                if sources_to_merge:
                    merge_assets(destination=destination_asset, sources=sources_to_merge)
            else:
                self.error(f"Unexpected asset name search response: {asset_name_json}")

            response = {
                "found_assets": list(found_assets),
                "created_asset": created_asset,
                "destination_asset": destination_asset,
            }
            responses.append(response)

        return {"data": responses}
