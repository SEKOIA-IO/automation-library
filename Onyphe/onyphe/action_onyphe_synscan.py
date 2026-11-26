from posixpath import join as urljoin

from sekoia_automation.action import Action

from onyphe.models import OnyphePagedIPArguments
from onyphe.utils import get_with_paging


class OnypheSynscanAction(Action):
    """
    Action to scan an IP for synscan information with Onyphe

    https://www.onyphe.io/blog/standard-information-categories/
    > Open TCP ports found on the Internet. Each open port is also enriched with detected operating system
    > (using our own TCP/IP stack fingerprinting technic). As of today, nearly 50 ports are scanned at least
    > once a month, but other ports may be scanned according to press releases.
    """

    def run(self, arguments: OnyphePagedIPArguments) -> dict:
        url: str = "https://www.onyphe.io/api/v2/simple/"
        get_url: str = urljoin(url, "synscan/" + str(arguments.ip))

        params = {"page": arguments.first_page}

        return get_with_paging(get_url, self.module.configuration, arguments.budget, params)
