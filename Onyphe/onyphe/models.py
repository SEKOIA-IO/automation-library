import ipaddress
import re
from typing import Annotated, Any

from pydantic import AfterValidator, BaseModel, BeforeValidator, Field, IPvAnyAddress


def reject_non_string(value: Any) -> Any:
    # IPvAnyAddress would otherwise turn an integer into an address (8 -> 0.0.0.8)
    if value is None or isinstance(value, (str, ipaddress.IPv4Address, ipaddress.IPv6Address)):
        return value
    raise ValueError("Input should be a string IP address")


def validate_domain(value: str) -> str:
    value = value.lower()  # Onyphe returns 404 on GOOGLE.COM
    # up to 253 chars, up to 127 sublevels of length up to 63
    if len(value) <= 253 and re.fullmatch(r"(?:[^.]{1,63}\.){1,127}[^.]{1,63}", value):
        return value
    raise ValueError("Input should be a valid domain")


def validate_md5(value: str) -> str:
    value = value.lower()
    if re.fullmatch(r"[0-9a-f]{32}", value):
        return value
    raise ValueError("Input should be a valid MD5 hash")


def validate_onion(value: str) -> str:
    value = value.lower()
    # 16 or 56 base32 characters followed by .onion
    if re.fullmatch(r"[2-7a-z]{16}(?:[2-7a-z]{40})?\.onion", value):
        return value
    raise ValueError("Input should be a valid onion address")


IPAddressArgument = Annotated[IPvAnyAddress, BeforeValidator(reject_non_string)]
DomainArgument = Annotated[str, AfterValidator(validate_domain)]
MD5Argument = Annotated[str, AfterValidator(validate_md5)]
OnionArgument = Annotated[str, AfterValidator(validate_onion)]


class OnypheIPArguments(BaseModel):
    ip: IPAddressArgument = Field(..., description="IP address to scan")


class OnyphePagingArguments(BaseModel):
    budget: int = Field(default=1, ge=0, description="Maximum number of pages to fetch, or 0 for all pages")
    first_page: int = Field(default=1, ge=1, description="First page number to fetch")


class OnyphePagedIPArguments(OnyphePagingArguments):
    ip: IPAddressArgument = Field(..., description="IP address to scan")


class OnypheDomainArguments(OnyphePagingArguments):
    domain: DomainArgument = Field(..., description="Domain to scan")


class OnypheMD5Arguments(OnyphePagingArguments):
    md5: MD5Argument = Field(..., description="MD5 hash to scan")


class OnypheOnionArguments(OnyphePagingArguments):
    onion: OnionArgument = Field(..., description="Onion address to scan")
