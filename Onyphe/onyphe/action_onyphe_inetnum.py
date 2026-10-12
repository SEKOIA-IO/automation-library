from posixpath import join as urljoin

from sekoia_automation.action import Action

from onyphe.models import OnyphePagedIPArguments
from onyphe.utils import get_with_paging


class OnypheInetnumAction(Action):
    """
    Action to scan an IP for inetnum information with Onyphe

    https://www.onyphe.io/blog/standard-information-categories/
    > IP (v4 and v6) networks description as given by RIRs (Regional Internet Registries),
    > except for the United States which does not disclose that information publicly.
    """

    def run(self, arguments: OnyphePagedIPArguments) -> dict:
        url: str = "https://www.onyphe.io/api/v2/simple/"
        get_url: str = urljoin(url, "inetnum/" + str(arguments.ip))

        params = {"page": arguments.first_page}

        return get_with_paging(get_url, self.module.configuration, arguments.budget, params)
