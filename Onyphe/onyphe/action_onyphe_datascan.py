import ipaddress
from posixpath import join as urljoin
from typing import Annotated

from pydantic import (
    BaseModel,
    BeforeValidator,
    Field,
    IPvAnyAddress,
    StringConstraints,
    model_validator,
)
from sekoia_automation.action import Action

from onyphe.utils import get_with_paging


def prepare_ip(value: str | ipaddress.IPv4Address | ipaddress.IPv6Address | None):
    if isinstance(value, str):
        return value.strip()
    if value is None or isinstance(value, (ipaddress.IPv4Address, ipaddress.IPv6Address)):
        return value
    raise ValueError("Input should be a string IP address")


NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
StrippedIPvAnyAddress = Annotated[IPvAnyAddress, BeforeValidator(prepare_ip)]


class OnypheDatascanArguments(BaseModel):
    ip: StrippedIPvAnyAddress | None = Field(default=None, description="IP address to scan")
    string: NonEmptyStr | None = Field(default=None, description="String to scan")
    budget: int = Field(default=1, description="Maximum number of pages to fetch, or 0 for all pages")
    first_page: int = Field(default=1, description="First page number to fetch")

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

    def run(self, arguments: OnypheDatascanArguments) -> dict | None:
        url: str = "https://www.onyphe.io/api/v2/simple/"
        resource = str(arguments.ip) if arguments.ip is not None else arguments.string
        assert resource is not None

        get_url: str = urljoin(url, "datascan/" + resource)

        params = {"page": arguments.first_page}

        return get_with_paging(get_url, self.module.configuration, arguments.budget, params)
