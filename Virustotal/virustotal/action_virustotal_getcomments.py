from posixpath import join as urljoin

import requests
from pydantic import BaseModel, Field
from requests import Response
from sekoia_automation.action import Action


class VirusTotalGetCommentsArguments(BaseModel):
    resource: str = Field(..., min_length=1, description="Resource to get comments for")


class VirusTotalGetCommentsAction(Action):
    """
    Action to get comments from VirusTotal
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def run(self, arguments: VirusTotalGetCommentsArguments) -> dict:
        resource = arguments.resource

        url: str = "https://www.virustotal.com/vtapi/v2/"
        get_url: str = urljoin(url, "comments/get")
        params: dict = {
            "apikey": self.module.configuration.get("apikey"),
            "resource": resource,
        }

        # Get comments from Virus Total
        response: Response = requests.get(get_url, params=params)
        response.raise_for_status()

        return response.json()
