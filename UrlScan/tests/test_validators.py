import pytest

from tests.payloads import BASE, SCAN_ID
from urlscan_modules.base import ActionError
from urlscan_modules.validators import internal_target_reason, valid_scan_id

REFUSED = [
    "http://127.0.0.1/", "http://10.0.0.1/", "http://192.168.1.10:8080/x", "http://169.254.169.254/latest",
    "http://100.64.0.1/", "http://0.0.0.0/", "http://[::1]/", "http://[fe80::1%25eth0]/",
    "http://[::ffff:10.0.0.1]/", "http://[64:ff9b::10.0.0.1]/", "http://[::10.0.0.1]/", "http://[2002:0a00:0001::1]/",
    "http://127.1/", "http://2130706433/", "http://0x7f.0.0.1/", "http://10.1.1/", "http://192.168.001.001/",
    "http://localhost/", "HTTP://LOCALHOST./", "http://fileserver/", "http://printer.local/", "http://db.internal/",
    "http://app.localhost/", "http://router.home.arpa/",
    "http://10.0.0.1\\@example.com/", "http:\\\\10.0.0.1\\x", "http://%31%30.0.0.1/", "http://\uff11\uff10.0.0.1/",
    "http:///10.0.0.1/", "//10.0.0.1/", "file:///etc/passwd",
    "10.0.0.1/admin", " http://10.0.0.1 ", "http://user:pw@10.0.0.1/",
]  # fmt: skip
ACCEPTED = [
    "https://example.com/", "example.com/path", " https://example.com ", "http://8.8.8.8/",
    "http://[2606:4700::6812:179a]/", "http://[::ffff:8.8.8.8]/", "http://[64:ff9b::8.8.8.8]/",
    "http://paypal.com@evil.example/login", "https://123.example.com/",
]  # fmt: skip
SUFFIX = "and will not be sent to urlscan.io"


@pytest.mark.parametrize("url", REFUSED)
def test_internal_target_refused(url):
    assert internal_target_reason(url).endswith(SUFFIX)


@pytest.mark.parametrize("url", ACCEPTED)
def test_public_target_accepted(url):
    assert internal_target_reason(url) is None


@pytest.mark.parametrize(
    "url, reason",
    [
        ("http://user:pw@10.0.0.1/", f"The URL host '10.0.0.1' is a private address {SUFFIX}"),
        ("http://[64:ff9b::10.0.0.1]/", f"The URL host '64:ff9b::10.0.0.1' is a private address {SUFFIX}"),
        ("http://127.1/", f"The URL host '127.1' is an IP address written in an unusual form {SUFFIX}"),
        ("http://fileserver/", f"The URL host 'fileserver' only exists inside a network {SUFFIX}"),
        ("file:///etc/passwd", f"The URL has no valid host {SUFFIX}"),
    ],
)
def test_reasons(url, reason):
    assert internal_target_reason(url) == reason


@pytest.mark.parametrize("value", [SCAN_ID, f"  {SCAN_ID.upper()} "])
def test_valid_scan_id(value):
    assert valid_scan_id(value) == SCAN_ID


@pytest.mark.parametrize("value", ["", None, "../../etc/passwd", f"{BASE}/result/{SCAN_ID}/", "0" * 32])
def test_invalid_scan_id(value):
    with pytest.raises(ActionError, match="is not a valid scan UUID"):
        valid_scan_id(value)
