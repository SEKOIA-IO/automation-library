from posixpath import join as urljoin

from sekoia_automation.action import Action

from onyphe.models import OnyphePagedIPArguments
from onyphe.utils import get_with_paging


class OnyphePastriesAction(Action):
    """
    Action to scan an IP for pastries information with Onyphe

    https://www.onyphe.io/blog/standard-information-categories/
    > Content of pasties collected in a continuous mode. As of today,
    > only pastebin is collected. Each collected pastie is enriched with DNS
    > information (where applicable). That is, you can search for an IP address
    > in pastries category and you may find pasties linked to it, even though
    > only an URL was contained in the original pastie. Same is true for domain
    > name or many other DNS-related information.
    """

    def run(self, arguments: OnyphePagedIPArguments) -> dict:
        url: str = "https://www.onyphe.io/api/v2/simple/"
        get_url: str = urljoin(url, "pastries/" + str(arguments.ip))

        params = {"page": arguments.first_page}

        return get_with_paging(get_url, self.module.configuration, arguments.budget, params)
