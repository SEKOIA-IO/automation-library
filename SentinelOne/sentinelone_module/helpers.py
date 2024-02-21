import re
import secrets
import string
from datetime import UTC, datetime


def camelize(string: str) -> str:
    return re.sub(r"_(.)", lambda m: m.group(1).upper(), string)


RFC3339_STRICT_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


def to_rfc3339(date: datetime):
    """
    Return the datetime as RFC3339 strict format
    """
    assert date.tzinfo is not None and date.tzinfo.utcoffset(date) is not None
    return date.astimezone(UTC).strftime(RFC3339_STRICT_FORMAT)


def generate_password(length: int = 64) -> str:
    alphabet = string.ascii_letters + string.digits + string.punctuation

    while True:
        candidate = "".join(secrets.choice(alphabet) for i in range(max(10, length)))
        if (
            any(c.islower() for c in candidate)
            and any(c.isupper() for c in candidate)
            and any(c.isdigit() for c in candidate)
            and any(True if c in string.punctuation else False for c in candidate)
        ):
            return candidate
