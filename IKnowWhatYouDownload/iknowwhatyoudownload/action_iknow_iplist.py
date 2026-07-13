from posixpath import join as urljoin

import requests
from pydantic import BaseModel, Field, IPvAnyNetwork
from requests import Response
from sekoia_automation.action import Action


class IKnowIPListArguments(BaseModel):
    cidr: IPvAnyNetwork = Field(..., description="CIDR to look up")


class IKnowIPListAction(Action):
    """
    Action to retrieve the list of IP peers in a CIDR
    """

    def run(self, arguments: IKnowIPListArguments) -> dict | None:
        url: str = self.module.configuration["host"]

        get_url: str = urljoin(url, "history/peers")
        params: dict = {
            "key": self.module.configuration.get("key"),
            "cidr": str(arguments.cidr),
        }

        # Fetch the report
        response: Response = requests.get(get_url, params=params)
        response.raise_for_status()

        payload = response.json()

        if "error" in payload:
            self.error(message=payload.get("message"))
            return None
        return payload
