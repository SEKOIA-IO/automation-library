from datetime import datetime
import re
from re import Pattern

_main_domain_regex = r"[-.\\\\\.\w[\]]+[()\[\]]?\.[()\[\]]?[\w-]+"

IPV4_ADDRESS_REGEX = re.compile(
    r"(?P<search>((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)"
    r"[.()\[\],\\]{1,3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)"
    r"[.()\[\],\\]{1,3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)"
    r"[.()\[\],\\]{1,3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)))",
    re.UNICODE,
)

IPV6_ADDRESS_REGEX = re.compile(
    r"(?P<search>("
    r"([0-9a-fA-F]{1,4}:){7,7}[0-9a-fA-F]{1,4}|"  # 1:2:3:4:5:6:7:8
    r"([0-9a-fA-F]{1,4}:){1,7}:|"  # 1::                              1:2:3:4:5:6:7::
    r"([0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}|"  # 1::8             1:2:3:4:5:6::8  1:2:3:4:5:6::8
    r"([0-9a-fA-F]{1,4}:){1,5}(:[0-9a-fA-F]{1,4}){1,2}|"  # 1::7:8           1:2:3:4:5::7:8  1:2:3:4:5::8
    r"([0-9a-fA-F]{1,4}:){1,4}(:[0-9a-fA-F]{1,4}){1,3}|"  # 1::6:7:8         1:2:3:4::6:7:8  1:2:3:4::8
    r"([0-9a-fA-F]{1,4}:){1,3}(:[0-9a-fA-F]{1,4}){1,4}|"  # 1::5:6:7:8       1:2:3::5:6:7:8  1:2:3::8
    r"([0-9a-fA-F]{1,4}:){1,2}(:[0-9a-fA-F]{1,4}){1,5}|"  # 1::4:5:6:7:8     1:2::4:5:6:7:8  1:2::8
    r"[0-9a-fA-F]{1,4}:((:[0-9a-fA-F]{1,4}){1,6})|"  # 1::3:4:5:6:7:8   1::3:4:5:6:7:8  1::8
    r":((:[0-9a-fA-F]{1,4}){1,7}|:)|"  # ::2:3:4:5:6:7:8  ::2:3:4:5:6:7:8 ::8       ::
    r"fe80:(:[0-9a-fA-F]{0,4}){0,4}%[0-9a-zA-Z]{1,}|"  # link-local IPv6 addresses with zone index
    r"::(ffff(:0{1,4}){0,1}:){0,1}"
    r"((25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])\.){3,3}"
    r"(25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])|"  # IPv4-mapped IPv6 addresses and IPv4-translated addresses
    r"([0-9a-fA-F]{1,4}:){1,4}:"
    r"((25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])\.){3,3}"
    r"(25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])"  # IPv4-Embedded IPv6 Address
    r"))",
    re.UNICODE,
)

DOMAIN_NAME_REGEX = re.compile(r"(?P<search>" + _main_domain_regex + ")", re.UNICODE)

URL_REGEX = re.compile(
    r"(?P<search>((?P<scheme>[\w\[\]]{2,9})\[?:\]?//\]?)([\S]*:[\S]*@)?(?P<hostname>"
    + _main_domain_regex
    + r")(:[\d]{1,5})?(?P<path>((/[^\s\"<]*)?(\?[^\s\"<]*)?(#[^\s\"<]*)?)[\w/])?)",
    re.UNICODE,
)

EMAIL_ADDRESS_REGEX = re.compile(
    r"(?P<search>[-.+\w!#%&'*=?^_`{|}~]+@(?P<domain>" + _main_domain_regex + "))",
    re.UNICODE,
)

MAC_ADDRESS_REGEX = re.compile(r"(?P<search>(([0-9A-Fa-f]{1,2}[.:-]){5,7}([0-9A-Fa-f]{1,2})))", re.UNICODE)

FILE_HASH_REGEX = re.compile(r"(?P<search>([a-fA-F0-9]{32,128}))", re.UNICODE)

OBSERVABLES_MAPPING: dict[str, Pattern] = {
    "ipv4-addr": IPV4_ADDRESS_REGEX,
    "ipv6-addr": IPV6_ADDRESS_REGEX,
    "domain-name": DOMAIN_NAME_REGEX,
    "url": URL_REGEX,
    "email-addr": EMAIL_ADDRESS_REGEX,
    "file": FILE_HASH_REGEX,
    "mac-addr": MAC_ADDRESS_REGEX,
}


def datetime_to_str(date: datetime) -> str:
    return date.strftime("%Y-%m-%dT%H:%M:%SZ")
