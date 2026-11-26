from posixpath import join as urljoin

import requests
from requests import Response
from sekoia_automation.action import Action

from onyphe.models import OnypheIPArguments


class OnypheGeolocAction(Action):
    """
    Action to geolocalize an IP with Onyphe
    """

    def run(self, arguments: OnypheIPArguments) -> dict:
        url: str = "https://www.onyphe.io/api/v2/simple/"
        get_url: str = urljoin(url, "geoloc/" + str(arguments.ip))

        response: Response = requests.get(get_url)
        response.raise_for_status()

        return response.json()
