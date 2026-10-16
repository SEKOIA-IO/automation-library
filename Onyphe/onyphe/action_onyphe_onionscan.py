from posixpath import join as urljoin

from sekoia_automation.action import Action

from onyphe.models import OnypheOnionArguments
from onyphe.utils import get_with_paging


class OnypheOnionscanAction(Action):
    """
    Action to scan an onion domain with Onyphe

    It seems that it is not part of the _free_ tier
    """

    def run(self, arguments: OnypheOnionArguments) -> dict:
        url: str = "https://www.onyphe.io/api/v2/simple/"
        get_url: str = urljoin(url, "onionscan/" + arguments.onion)

        params = {"page": arguments.first_page}

        return get_with_paging(get_url, self.module.configuration, arguments.budget, params)
