from posixpath import join as urljoin

from sekoia_automation.action import Action

from onyphe.utils import get_arg_ip, get_with_paging


class OnypheDatascanAction(Action):
    """
    Action to scan an IP or string for datascan information with Onyphe

    https://www.onyphe.io/blog/standard-information-categories/
    > Application responses to our application requests. Application requests
    > are performed against found open TCP ports, or directly to some UDP ports.
    > We are using our own technology for protocol identification. In fact,
    > we are able to recognize more than 40 different protocols (as of today).
    > Thanks to our methodology, instead of searching our data on a port-basis,
    > you can simply search by protocol instead.
    >
    > Furthermore, as well as crawling the clear Net for HTTP protocol,
    > we are also crawling the clear Web by using domain name information
    > when performing HTTP 1.1 requests with a valid HTTP Host header.
    > Thus, we are able to identify multiple virtual hosts on a unique IP address.
    """

    def run(self, arguments) -> dict:
        url: str = "https://www.onyphe.io/api/v2/simple/"
        if ("ip" in arguments) == ("string" in arguments):
            raise TypeError("Invalid number of arguments. Please specify exactly one of 'ip' or 'string'")

        if "ip" in arguments:
            resource = get_arg_ip(arguments)
        else:
            resource = arguments["string"]

        get_url: str = urljoin(url, "datascan/" + resource)

        budget = arguments.get("budget", 1)
        params = {"page": arguments.get("first_page", 1)}

        return get_with_paging(get_url, self.module.configuration, budget, params)
