from posixpath import join as urljoin

from sekoia_automation.action import Action

from onyphe.utils import get_arg_ip, get_with_paging


class OnypheReverseAction(Action):
    """
    Action to scan an IP for reverse DNS information with Onyphe

    https://www.onyphe.io/blog/standard-information-categories/
    > Each time an IP address (v4 or v6) or a host name is found in collected
    > information (whatever the source category), we perform DNS requests (both
    > forward and reverse). This passive DNS information is thus collected and
    > stored in this information category.
    """

    def run(self, arguments) -> dict:
        url: str = "https://www.onyphe.io/api/v2/simple/"
        ip = get_arg_ip(arguments)
        get_url: str = urljoin(url, "reverse/" + ip)

        budget = arguments.get("budget", 1)
        params = {"page": arguments.get("first_page", 1)}

        return get_with_paging(get_url, self.module.configuration, budget, params)
