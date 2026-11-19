from posixpath import join as urljoin

from sekoia_automation.action import Action

from onyphe.models import OnyphePagedIPArguments
from onyphe.utils import get_with_paging


class OnypheReverseAction(Action):
    """
    Action to scan an IP for reverse DNS information with Onyphe

    https://www.onyphe.io/blog/standard-information-categories/
    > Each time an IP address (v4 or v6) or a host name is found in collected
    > information (whatever the source category), we perform DNS requests (both
    > forward and reverse). This passive DNS information is thus collected and
    > stored in this information category.
    """

    def run(self, arguments: OnyphePagedIPArguments) -> dict:
        url: str = "https://www.onyphe.io/api/v2/simple/"
        get_url: str = urljoin(url, "reverse/" + str(arguments.ip))

        params = {"page": arguments.first_page}

        return get_with_paging(get_url, self.module.configuration, arguments.budget, params)
