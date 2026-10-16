from posixpath import join as urljoin

from sekoia_automation.action import Action

from onyphe.models import OnyphePagedIPArguments
from onyphe.utils import get_with_paging


class OnypheIpAction(Action):
    """
    Action to scan an IP with Onyphe
    """

    def run(self, arguments: OnyphePagedIPArguments) -> dict:
        url: str = "https://www.onyphe.io/api/v2/simple/"
        get_url: str = urljoin(url, "ip/" + str(arguments.ip))

        params = {"page": arguments.first_page}

        return get_with_paging(get_url, self.module.configuration, arguments.budget, params)
