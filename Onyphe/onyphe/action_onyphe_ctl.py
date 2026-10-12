from posixpath import join as urljoin

from sekoia_automation.action import Action

from onyphe.models import OnypheDomainArguments
from onyphe.utils import get_with_paging


class OnypheCtlAction(Action):
    """
    Action to scan a domain for ctl information with Onyphe

    https://www.onyphe.io/blog/standard-information-categories/
    > We collect some Certificate Transparency Logs (CTLs) X509 cerfificates
    > information. As with some other information categories, we perform DNS
    > requests (IP v4 and v6) to enrich collected data with DNS-related
    > information and also feed our passive DNS (resolver information category).
    """

    def run(self, arguments: OnypheDomainArguments) -> dict:
        url: str = "https://www.onyphe.io/api/v2/simple/"
        get_url: str = urljoin(url, "ctl/" + arguments.domain)

        params = {"page": arguments.first_page}

        return get_with_paging(get_url, self.module.configuration, arguments.budget, params)
