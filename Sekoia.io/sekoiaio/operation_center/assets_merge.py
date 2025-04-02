from typing import List
from posixpath import join as urljoin
from pydantic.v1 import BaseModel
import requests
from sekoia_automation.action import Action


class Arguments(BaseModel):
    destination: str
    sources: List[str]


class Response(BaseModel):
    status_code: int
    headers: dict
    text: str


class MergeAssets(Action):
    """
    Action to merge assets together
    """

    results_model = Response

    def run(self, arguments: Arguments) -> Response:
        sources = arguments.sources
        destination = arguments.destination
        self.log(
            message=f"Merge assets module started. Mergings Asset UUID(s) {sources} into Asset UUID: {destination}",
            level="info",
        )
        api_path = urljoin(self.module.configuration["base_url"], "v2/asset-management/assets/merge")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.module.configuration['api_key']}",
        }

        payload = {"destination": destination, "sources": sources}

        response = requests.request("POST", api_path, json=payload, headers=headers)

        if not response.ok:
            # Will end action as in error
            self.error(f"HTTP Request failed: {api_path} with {response.status_code}")

        return Response(
            status_code=response.status_code,
            headers=dict(response.headers),
            text=response.text,
        )
