from posixpath import join as urljoin

import requests
from pydantic import BaseModel, Field
from requests import Response
from sekoia_automation.action import Action

from virustotal.errors import DuplicateCommentError


class VirusTotalPostCommentArguments(BaseModel):
    resource: str = Field(..., min_length=1, description="Resource to post the comment on")
    comment: str = Field(..., min_length=1, description="Comment to post")


class VirusTotalPostCommentAction(Action):
    """
    Action to post a comment on a scan on VirusTotal
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def run(self, arguments: VirusTotalPostCommentArguments) -> dict | None:
        resource = arguments.resource
        comment = arguments.comment

        url: str = "https://www.virustotal.com/vtapi/v2/"
        upload_url: str = urljoin(url, "comments/put")
        params: dict = {
            "apikey": self.module.configuration.get("apikey"),
            "resource": resource,
            "comment": comment,
        }

        response: Response = requests.post(upload_url, params=params)
        response.raise_for_status()

        vt_response: dict = response.json()

        if vt_response["response_code"] == 0:
            raise DuplicateCommentError()

        return response.json()
