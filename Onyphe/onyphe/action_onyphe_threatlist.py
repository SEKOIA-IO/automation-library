from posixpath import join as urljoin

from sekoia_automation.action import Action

from onyphe.utils import get_arg_ip, get_with_paging


class OnypheThreatlistAction(Action):
    """
    Action to scan an IP for threatlist information with Onyphe

    https://www.onyphe.io/blog/standard-information-categories/
    > We collect and aggregate a fair number of open threat lists.
    > As of today, 25 lists are aggregated. We also have our own threat lists
    > based on our honeypots. For instance, we have dedicated Mirai and
    > Broadcom UPnP hunter botnet lists.
    """

    def run(self, arguments) -> dict:
        url: str = "https://www.onyphe.io/api/v2/simple/"
        ip = get_arg_ip(arguments)
        get_url: str = urljoin(url, "threatlist/" + ip)

        budget = arguments.get("budget", 1)
        params = {"page": arguments.get("first_page", 1)}

        return get_with_paging(get_url, self.module.configuration, budget, params)
