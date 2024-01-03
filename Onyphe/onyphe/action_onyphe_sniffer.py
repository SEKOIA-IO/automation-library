from posixpath import join as urljoin

from sekoia_automation.action import Action

from onyphe.utils import get_arg_ip, get_with_paging


class OnypheSnifferAction(Action):
    """
    Action to scan an IP for sniffer information with Onyphe

    https://www.onyphe.io/blog/standard-information-categories/
    > We have a number of distributed honeypots on the Internet.
    > We are listening to Internet background noise and performing
    > passive operating system identification (using our own TCP/IP
    > stack fingerprinting technic).
    >
    > Furthermore, when a malicious pattern is found, we are performing
    > a synscan along with a datascan to collect more information regarding
    > the source IP address. synscan, datascan, resolver and threatlist
    > information categories are enriched thanks to this information category.
    """

    def run(self, arguments) -> dict:
        url: str = "https://www.onyphe.io/api/v2/simple/"
        ip = get_arg_ip(arguments)
        get_url: str = urljoin(url, "sniffer/" + ip)

        budget = arguments.get("budget", 1)
        params = {"page": arguments.get("first_page", 1)}

        return get_with_paging(get_url, self.module.configuration, budget, params)
