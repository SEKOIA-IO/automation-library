from posixpath import join as urljoin

from sekoia_automation.action import Action

from onyphe.utils import get_arg_ip, get_with_paging


class OnypheInetnumAction(Action):
    """
    Action to scan an IP for inetnum information with Onyphe

    https://www.onyphe.io/blog/standard-information-categories/
    > IP (v4 and v6) networks description as given by RIRs (Regional Internet Registries),
    > except for the United States which does not disclose that information publicly.
    """

    def run(self, arguments) -> dict:
        url: str = "https://www.onyphe.io/api/v2/simple/"
        ip = get_arg_ip(arguments)
        get_url: str = urljoin(url, "inetnum/" + ip)

        budget = arguments.get("budget", 1)
        params = {"page": arguments.get("first_page", 1)}

        return get_with_paging(get_url, self.module.configuration, budget, params)
