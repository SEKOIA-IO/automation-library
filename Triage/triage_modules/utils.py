from datetime import datetime
import re

_main_domain_regex = r"[-.\\\\\.\w[\]]+[()\[\]]?\.[()\[\]]?[\w-]+"

IPV4_ADDRESS_REGEX = re.compile(
    r"(?P<search>((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)"
    r"[.()\[\],\\]{1,3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)"
    r"[.()\[\],\\]{1,3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)"
    r"[.()\[\],\\]{1,3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)))",
    re.UNICODE,
)

URL_REGEX = re.compile(
    r"(?P<search>((?P<scheme>[\w\[\]]{2,9})\[?:\]?//\]?)([\S]*:[\S]*@)?(?P<hostname>"
    + _main_domain_regex
    + r")(:[\d]{1,5})?(?P<path>((/[^\s\"<]*)?(\?[^\s\"<]*)?(#[^\s\"<]*)?)[\w/])?)",
    re.UNICODE,
)


def datetime_to_str(date: datetime) -> str:
    return date.strftime("%Y-%m-%dT%H:%M:%SZ")
