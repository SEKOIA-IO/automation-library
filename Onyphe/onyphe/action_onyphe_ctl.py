from posixpath import join as urljoin

from sekoia_automation.action import Action

from onyphe.utils import get_arg_domain, get_with_paging


class OnypheCtlAction(Action):
    """
    Action to scan a domain for ctl information with Onyphe

    https://www.onyphe.io/blog/standard-information-categories/
    > We collect some Certificate Transparency Logs (CTLs) X509 cerfificates
    > information. As with some other information categories, we perform DNS
    > requests (IP v4 and v6) to enrich collected data with DNS-related
    > information and also feed our passive DNS (resolver information category).
    """

    def run(self, arguments) -> dict:
        url: str = "https://www.onyphe.io/api/v2/simple/"
        domain = get_arg_domain(arguments)
        get_url: str = urljoin(url, "ctl/" + domain)

        budget = arguments.get("budget", 1)
        params = {"page": arguments.get("first_page", 1)}

        return get_with_paging(get_url, self.module.configuration, budget, params)
