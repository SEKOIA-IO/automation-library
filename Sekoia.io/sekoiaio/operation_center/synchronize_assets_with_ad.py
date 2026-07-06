import json
from functools import cached_property
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import requests
from pydantic.v1 import BaseModel
from sekoia_automation.action import Action


class UnexpectedJSONResponseError(Exception):
    def __init__(self, request_name: str, url: str, status_code: int, content_type: str, body: str):
        self.request_name = request_name
        self.url = url
        self.status_code = status_code
        self.content_type = content_type
        self.body = body
        super().__init__(str(self))

    def __str__(self) -> str:
        return (
            f"Expected JSON response for {self.request_name}: {self.url} "
            f"with status code {self.status_code}, content type {self.content_type}, body: {self.body}"
        )


class Arguments(BaseModel):
    user_ad_data: Optional[Dict[str, Any]] = None
    asset_synchronization_configuration: Dict[str, Any]
    community_uuid: str
    user_ad_file: Optional[str] = None


class SynchronizeAssetsWithAD(Action):
    """
    Action to synchronize asset with Active Directory (AD).
    """

    @cached_property
    def base_url(self) -> str:
        return self.module.configuration.get("base_url", "").rstrip("/")

    @cached_property
    def api_key(self) -> str:
        return self.module.configuration.get("api_key", "")

    @cached_property
    def session(self) -> requests.Session:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        session = requests.Session()
        session.headers.update(headers)

        return session

    def _parse_json_response(self, response: requests.Response, request_name: str) -> Any:
        try:
            return response.json()
        except ValueError:
            response_text = response.text.strip() or "<empty response>"
            content_type = response.headers.get("Content-Type", "unknown")
            error_message = UnexpectedJSONResponseError(
                request_name=request_name,
                url=response.url,
                status_code=response.status_code,
                content_type=content_type,
                body=response_text,
            )
            self.log(
                str(error_message),
                level="error",
                request_name=request_name,
                url=response.url,
                status_code=response.status_code,
                content_type=content_type,
                body=response_text,
            )
            self.error(str(error_message))
            return None

    def get_assets(self, search_query: str, also_search_in_detection_properties: bool = False) -> Any:
        params = {"search": search_query}
        if also_search_in_detection_properties:
            params["also_search_in_detection_properties"] = "true"

        api_path = urljoin(self.base_url + "/", "v2/asset-management/assets")
        response = self.session.get(api_path, params=params)
        if not response.ok:
            self.error(
                f"HTTP GET request failed: {response.url} with status code "
                f"{response.status_code} - {response.reason} : {response.text}"
            )
            return None

        return self._parse_json_response(response, "GET assets")

    def post_request(self, endpoint: str, json_data: str) -> Any:
        api_path = urljoin(self.base_url + "/", endpoint)
        response = self.session.post(api_path, data=json_data)
        if not response.ok:
            self.error(
                f"HTTP POST request failed: {api_path} with status code "
                f"{response.status_code} - {response.reason} : {response.text}"
            )
            return None

        return self._parse_json_response(response, f"POST {endpoint}")

    def put_request(self, endpoint: str, json_data: str) -> None:
        api_path = urljoin(self.base_url + "/", endpoint)
        response = self.session.put(api_path, data=json_data)
        if not response.ok:
            self.error(
                f"HTTP PUT request failed: {api_path} with status code "
                f"{response.status_code} - {response.reason} : {response.text}"
            )
            return

    def merge_assets(self, destination: str, sources: List[str]) -> None:
        api_path = urljoin(self.base_url + "/", "v2/asset-management/assets/merge")
        payload = {"destination": destination, "sources": sources}
        response = self.session.post(api_path, json=payload)
        if not response.ok:
            self.error(
                f"HTTP POST merge request failed: {api_path} with status code "
                f"{response.status_code} - {response.reason} : {response.text}"
            )
            return

    def run(self, arguments: dict) -> Optional[Dict[str, List[Dict[str, Any]]]]:
        responses: List[Dict[str, Any]] = []
        asset_conf = arguments["asset_synchronization_configuration"]
        community_uuid = arguments["community_uuid"]
        user_ad_data = self.json_argument("user_ad_data", arguments)

        if not isinstance(user_ad_data, list):
            user_ad_data = [user_ad_data]

        if not self.base_url or not self.api_key:
            self.error("Configuration must include base_url and api_key.")
            return None

        asset_name_field = asset_conf.get("asset_name_field")
        if not asset_name_field:
            self.error("Configuration must include asset_name_field.")
            return None

        assert isinstance(asset_name_field, str)

        for index, single_user_ad_data in enumerate(user_ad_data, start=1):
            self.log(f"Processing user_ad_data item {index}/{len(user_ad_data)}")

            asset_name = single_user_ad_data.get(asset_name_field)
            if not asset_name:
                self.error(f"User AD data does not contain the asset_name_field: {asset_name_field}.")
                return None

            assert isinstance(asset_name, str)

            asset_name_json = self.get_assets(search_query=asset_name)
            if asset_name_json is None:
                return None

            detection_properties_config = asset_conf.get("detection_properties", {})
            found_assets = set()

            for prop, keys in detection_properties_config.items():
                for key in keys:
                    value = single_user_ad_data.get(key)
                    if value:
                        assets = self.get_assets(search_query=value, also_search_in_detection_properties=True)
                        if assets is None:
                            return None
                        if assets.get("total", 0) > 0:
                            for asset in assets.get("items", []):
                                found_assets.add(asset["uuid"])

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
                    found_assets.add(asset_uuid)

                    sources_to_merge = list(found_assets - {destination_asset})
                    if sources_to_merge:
                        previous_error_message = self.error_message
                        self.merge_assets(destination=destination_asset, sources=sources_to_merge)
                        if self.error_message != previous_error_message:
                            return None

                    endpoint = f"v2/asset-management/assets/{destination_asset}"
                    self.log(f"PUT request: {endpoint} and payload asset is {json_payload_asset}")
                    previous_error_message = self.error_message
                    self.put_request(endpoint=endpoint, json_data=json_payload_asset)
                    if self.error_message != previous_error_message:
                        return None
                else:
                    self.error(f"Unexpected asset name search response: {asset_name_json}")
                    return None
            elif asset_name_json.get("total", 0) == 0:
                created_asset = True
                payload_asset["community_uuid"] = community_uuid
                create_response = self.post_request(
                    endpoint="v2/asset-management/assets", json_data=json.dumps(payload_asset)
                )
                if create_response is None:
                    return None

                destination_asset = create_response.get("uuid", "")
                if destination_asset == "":
                    self.error("Asset creation response does not contain uuid.")
                    return None

                sources_to_merge = list(found_assets)
                if sources_to_merge:
                    previous_error_message = self.error_message
                    self.merge_assets(destination=destination_asset, sources=sources_to_merge)
                    if self.error_message != previous_error_message:
                        return None
            else:
                self.error(f"Unexpected asset name search response: {asset_name_json}")
                return None

            response = {
                "found_assets": list(found_assets),
                "created_asset": created_asset,
                "destination_asset": destination_asset,
            }
            responses.append(response)

        return {"data": responses}
