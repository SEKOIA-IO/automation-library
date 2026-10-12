from posixpath import join as urljoin

from pydantic import Field, model_validator
from sekoia_automation.action import Action

from onyphe.models import IPAddressArgument, OnyphePagingArguments
from onyphe.utils import get_with_paging


class OnypheDatascanArguments(OnyphePagingArguments):
    ip: IPAddressArgument | None = Field(default=None, description="IP address to scan")
    string: str | None = Field(default=None, min_length=1, description="String to scan")

    @model_validator(mode="after")
    def validate_entrypoint(self) -> "OnypheDatascanArguments":
        if (self.ip is None) == (self.string is None):
            raise ValueError("Please specify exactly one of 'ip' or 'string'")
        return self


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

    def run(self, arguments: OnypheDatascanArguments) -> dict:
        url: str = "https://www.onyphe.io/api/v2/simple/"
        if arguments.ip is not None:
            resource = str(arguments.ip)
        elif arguments.string is not None:
            resource = arguments.string
        else:
            raise ValueError("Please specify exactly one of 'ip' or 'string'")

        get_url: str = urljoin(url, "datascan/" + resource)

        params = {"page": arguments.first_page}

        return get_with_paging(get_url, self.module.configuration, arguments.budget, params)
