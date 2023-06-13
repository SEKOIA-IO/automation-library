import ipaddress
from typing import Any


def is_valid(observable_type: str, path: str, value: Any) -> bool:
    full_path = f"{observable_type}:{'.'.join(path)}"

    if full_path in VALIDATORS:
        return VALIDATORS[full_path](value)

    return True


def ipv4_validator(value: str) -> bool:
    try:
        ipaddress.IPv4Network(value)
        return True
    except ipaddress.AddressValueError:
        return False


def ipv6_validator(value: str) -> bool:
    try:
        ipaddress.IPv6Network(value)
        return True
    except ipaddress.AddressValueError:
        return False


VALIDATORS = {"ipv4-addr:value": ipv4_validator, "ipv6-addr:value": ipv6_validator}
