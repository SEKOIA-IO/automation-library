from posixpath import join as urljoin

from sekoia_automation.action import Action

from onyphe.models import OnyphePagedIPArguments
from onyphe.utils import get_with_paging


class OnypheThreatlistAction(Action):
    """
    Action to scan an IP for threatlist information with Onyphe

    https://www.onyphe.io/blog/standard-information-categories/
    > We collect and aggregate a fair number of open threat lists.
    > As of today, 25 lists are aggregated. We also have our own threat lists
    > based on our honeypots. For instance, we have dedicated Mirai and
    > Broadcom UPnP hunter botnet lists.
    """

    def run(self, arguments: OnyphePagedIPArguments) -> dict:
        url: str = "https://www.onyphe.io/api/v2/simple/"
        get_url: str = urljoin(url, "threatlist/" + str(arguments.ip))

        params = {"page": arguments.first_page}

        return get_with_paging(get_url, self.module.configuration, arguments.budget, params)
