from posixpath import join as urljoin

import requests
from requests import Response
from sekoia_automation.action import Action

from onyphe.utils import get_arg_ip


class OnypheGeolocAction(Action):
    """
    Action to geolocalize an IP with Onyphe
    """

    def run(self, arguments) -> dict:
        url: str = "https://www.onyphe.io/api/v2/simple/"
        ip = get_arg_ip(arguments)
        get_url: str = urljoin(url, "geoloc/" + ip)

        response: Response = requests.get(get_url)
        response.raise_for_status()

        return response.json()
