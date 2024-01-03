from posixpath import join as urljoin

from sekoia_automation.action import Action

from onyphe.utils import get_arg_onion, get_with_paging


class OnypheOnionscanAction(Action):
    """
    Action to scan an onion domain with Onyphe

    It seems that it is not part of the _free_ tier
    """

    def run(self, arguments) -> dict:
        url: str = "https://www.onyphe.io/api/v2/simple/"
        onion = get_arg_onion(arguments)
        get_url: str = urljoin(url, "onionscan/" + onion)

        budget = arguments.get("budget", 1)
        params = {"page": arguments.get("first_page", 1)}

        return get_with_paging(get_url, self.module.configuration, budget, params)
