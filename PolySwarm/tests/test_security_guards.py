"""Guards against the two failure modes that make this module unsafe in a SOC.

1. A playbook must not be able to name a path outside the run data directory.
   The container holds the credentials of the run itself, and an action that
   opens whatever path it is handed uploads them to the configured community.
2. A scan without a verdict must not be reported as a finished scan. An open
   assertion window, a failed scan and an abstaining engine all look like
   "clean" if their counts are taken at face value.


Every action builds its client through polyswarm_modules.client, so that is the
single place these tests patch, rather than each action's own module.
"""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from polyswarm_modules import PolyswarmModule
from polyswarm_modules.action_polyswarm_sandboxfile import SandboxFile
from polyswarm_modules.action_polyswarm_scanfile import ScanFile
from polyswarm_modules.action_polyswarm_scanip import ScanIp
from polyswarm_modules.action_polyswarm_scanurl import ScanUrl


@pytest.fixture
def scan_file(data_storage: str, module: PolyswarmModule) -> ScanFile:
    return ScanFile(module=module, data_path=data_storage)


@pytest.fixture
def sample_file(data_storage: str) -> str:
    path = Path(data_storage) / "malware.exe"
    path.write_bytes(b"sample bytes")
    return path.name


def _assertion(verdict: bool | None, *, name: str = "Engine", mask: bool = True) -> MagicMock:
    assertion = MagicMock()
    assertion.engine_name = name
    assertion.author_name = name.lower()
    assertion.verdict = verdict
    assertion.mask = mask
    return assertion


def _result(
    *, failed: bool = False, window_closed: bool = True, assertions: list[MagicMock] | None = None
) -> MagicMock:
    assertions = assertions if assertions is not None else [_assertion(True)]
    result = MagicMock()
    result.sha256 = "ab" * 32
    result.sha1 = "cd" * 20
    result.md5 = "ef" * 16
    result.extended_type = "PE32 executable"
    result.polyscore = 0.9
    result.permalink = "https://polyswarm.network/scan/results/test"
    result.failed = failed
    result.window_closed = window_closed
    result.assertions = assertions
    return result


# --- guard 1: the file a playbook names stays inside the run data directory ---


@patch("polyswarm_modules.client.PolyswarmAPI", autospec=True)
def test_absolute_path_is_refused(mock_api_class: MagicMock, scan_file: ScanFile) -> None:
    """The Sekoia run token lives at a known absolute path in the container."""
    response = scan_file.run({"file": "/symphony/token"})

    assert response is None
    assert "relative" in scan_file.error_message
    mock_api_class.return_value.submit.assert_not_called()


@patch("polyswarm_modules.client.PolyswarmAPI", autospec=True)
def test_parent_traversal_is_refused(mock_api_class: MagicMock, scan_file: ScanFile) -> None:
    response = scan_file.run({"file": "../../../etc/passwd"})

    assert response is None
    assert "outside" in scan_file.error_message
    mock_api_class.return_value.submit.assert_not_called()


@patch("polyswarm_modules.client.PolyswarmAPI", autospec=True)
def test_symlink_out_of_the_data_directory_is_refused(
    mock_api_class: MagicMock, scan_file: ScanFile, data_storage: str
) -> None:
    outside = Path(data_storage).parent / "outside-secret"
    outside.write_bytes(b"a credential")
    link = Path(data_storage) / "innocent.txt"
    os.symlink(outside, link)

    try:
        response = scan_file.run({"file": link.name})
    finally:
        outside.unlink()

    assert response is None
    assert "outside" in scan_file.error_message
    mock_api_class.return_value.submit.assert_not_called()


@patch("polyswarm_modules.client.PolyswarmAPI", autospec=True)
def test_missing_file_is_refused(mock_api_class: MagicMock, scan_file: ScanFile) -> None:
    response = scan_file.run({"file": "never-delivered.bin"})

    assert response is None
    assert "not found" in scan_file.error_message
    mock_api_class.return_value.submit.assert_not_called()


@patch("polyswarm_modules.client.PolyswarmAPI", autospec=True)
def test_sandbox_file_refuses_an_absolute_path(
    mock_api_class: MagicMock, data_storage: str, module: PolyswarmModule
) -> None:
    """Detonation takes a file argument now that the report action only reads."""
    action = SandboxFile(module=module, data_path=data_storage)

    response = action.run({"file": "/symphony/token"})

    assert response is None
    assert "relative" in action.error_message
    mock_api_class.return_value.sandbox_file.assert_not_called()


# --- guard 2: no verdict is not the same as a clean verdict ---


@patch("polyswarm_modules.client.PolyswarmAPI", autospec=True)
def test_scan_still_in_flight_is_not_served_as_cached(
    mock_api_class: MagicMock, scan_file: ScanFile, sample_file: str
) -> None:
    """Someone else submitted this sample seconds ago and no engine has answered."""
    in_flight = _result(window_closed=False, assertions=[])
    mock_api = mock_api_class.return_value
    mock_api.search.return_value = [in_flight]
    mock_api.submit.return_value = MagicMock()
    mock_api.lookup.return_value = _result()

    response = scan_file.run({"file": sample_file})

    mock_api.submit.assert_called_once()
    assert response["cached"] is False
    assert response["malicious_count"] == 1


@patch("polyswarm_modules.client.PolyswarmAPI", autospec=True)
def test_failed_scan_errors_instead_of_reporting_zero_detections(
    mock_api_class: MagicMock, scan_file: ScanFile, sample_file: str
) -> None:
    mock_api = mock_api_class.return_value
    mock_api.search.return_value = []
    mock_api.submit.return_value = MagicMock()
    mock_api.lookup.return_value = _result(failed=True, assertions=[])

    response = scan_file.run({"file": sample_file})

    assert response is None
    assert "failed" in scan_file.error_message


@patch("polyswarm_modules.action_polyswarm_scanfile.wait_for_scan")
@patch("polyswarm_modules.client.PolyswarmAPI", autospec=True)
def test_open_window_after_waiting_errors(
    mock_api_class: MagicMock, mock_wait: MagicMock, scan_file: ScanFile, sample_file: str
) -> None:
    """The wait helper only returns on a closed window, so this guards a result that gets past it anyway."""
    mock_api = mock_api_class.return_value
    mock_api.search.return_value = []
    mock_api.submit.return_value = MagicMock()
    mock_wait.return_value = _result(window_closed=False, assertions=[])

    response = scan_file.run({"file": sample_file})

    assert response is None
    assert "still open" in scan_file.error_message


@patch("polyswarm_modules.client.PolyswarmAPI", autospec=True)
def test_abstaining_engine_is_not_counted_as_benign(
    mock_api_class: MagicMock, scan_file: ScanFile, sample_file: str
) -> None:
    assertions = [_assertion(True, name="ClamAV"), _assertion(None, name="Abstainer"), _assertion(False, name="Clean")]
    mock_api = mock_api_class.return_value
    mock_api.search.return_value = []
    mock_api.submit.return_value = MagicMock()
    mock_api.lookup.return_value = _result(assertions=assertions)

    response = scan_file.run({"file": sample_file})

    assert response["malicious_count"] == 1
    assert response["benign_count"] == 1
    assert response["total_count"] == 3


@patch("polyswarm_modules.client.PolyswarmAPI", autospec=True)
def test_url_scan_in_flight_is_not_served_as_cached(
    mock_api_class: MagicMock, data_storage: str, module: PolyswarmModule
) -> None:
    action = ScanUrl(module=module, data_path=data_storage)
    mock_api = mock_api_class.return_value
    mock_api.search_url.return_value = [_result(window_closed=False, assertions=[])]
    mock_api.submit.return_value = MagicMock()
    mock_api.lookup.return_value = _result()

    response = action.run({"url": "https://example.com"})

    mock_api.submit.assert_called_once()
    assert response["cached"] is False


@patch("polyswarm_modules.client.PolyswarmAPI", autospec=True)
def test_ip_scan_failed_result_errors(mock_api_class: MagicMock, data_storage: str, module: PolyswarmModule) -> None:
    action = ScanIp(module=module, data_path=data_storage)
    mock_api = mock_api_class.return_value
    mock_api.search_url.return_value = []
    mock_api.submit.return_value = MagicMock()
    mock_api.lookup.return_value = _result(failed=True, assertions=[])

    response = action.run({"ip": "8.8.8.8"})

    assert response is None
    assert "failed" in action.error_message


@pytest.mark.parametrize(
    "url",
    [
        "http://10.0.0.1/internal-admin/",
        "https://192.168.1.5:8443/login",
        "http://172.16.0.9/",
        "http://[::1]/",
        "http://[fd00::1]:8080/x",
        "http://127.0.0.1/",
        "http://169.254.169.254/latest/meta-data/",
        "http://user:secret@10.0.0.1/",
        "http://224.0.0.1/",
        "http://100.64.0.1/",
        "http://[::ffff:10.0.0.1]/",
        "http://localhost/",
        "http://LOCALHOST:8080/",
        "http://app.localhost/",
        "http://fileserver/share",
        "http://fileserver.:8080/",
        "http://127.1/",
        "http://2130706433/",
        "http://0x7f.0.0.1/",
        "http:///nohost",
    ],
)
def test_internal_url_is_refused(url: str) -> None:
    from polyswarm_modules.validators import invalid_url_reason

    reason = invalid_url_reason(url)

    assert reason is not None
    assert "secret" not in reason


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com/",
        "https://sub.example.co.uk:8443/a?b=c#d",
        "https://user:pw@example.com/path",
        "http://8.8.8.8/",
        "http://8.8.8.8:8080/x",
        "http://[2606:4700:4700::1111]/",
        "http://example.com./",
    ],
)
def test_public_url_is_allowed(url: str) -> None:
    from polyswarm_modules.validators import invalid_url_reason

    assert invalid_url_reason(url) is None


def test_url_refusal_names_the_address_and_the_consequence() -> None:
    from polyswarm_modules.validators import invalid_url_reason

    assert invalid_url_reason("http://10.0.0.1/x") == (
        "The URL points at a private address '10.0.0.1' and will not be sent to PolySwarm's public community"
    )


def test_scheme_is_still_checked_first() -> None:
    from polyswarm_modules.validators import invalid_url_reason

    assert "scheme" in (invalid_url_reason("ftp://example.com/") or "")


@pytest.mark.parametrize("ip", ["224.0.0.1", "ff02::1", "100.64.0.1", "100.127.255.254"])
def test_multicast_and_shared_address_space_ips_are_refused(ip: str) -> None:
    from polyswarm_modules.validators import invalid_ip_reason

    assert invalid_ip_reason(ip) is not None


@pytest.mark.parametrize("ip", ["8.8.8.8", "1.1.1.1", "2606:4700:4700::1111"])
def test_public_ips_are_still_allowed(ip: str) -> None:
    from polyswarm_modules.validators import invalid_ip_reason

    assert invalid_ip_reason(ip) is None


@patch("polyswarm_modules.client.PolyswarmAPI", autospec=True)
def test_url_scan_of_an_internal_host_never_reaches_the_api(
    mock_api_class: MagicMock, data_storage: str, module: PolyswarmModule
) -> None:
    action = ScanUrl(module=module, data_path=data_storage)

    response = action.run({"url": "http://10.0.0.1/internal-admin/"})

    assert response is None
    assert "public community" in action.error_message
    mock_api_class.return_value.submit.assert_not_called()


@pytest.mark.parametrize(
    "url",
    [
        "http://printer.local/",
        "https://wiki.internal/",
        "http://nas.home.arpa/",
    ],
)
def test_reserved_private_suffixes_are_refused(url: str) -> None:
    from polyswarm_modules.validators import invalid_url_reason

    assert "only exists inside a network" in (invalid_url_reason(url) or "")


@pytest.mark.parametrize(
    "url",
    [
        "ftp://user:secret@example.com/",
        "gopher://user:secret@example.com/",
    ],
)
def test_a_refused_scheme_does_not_echo_credentials(url: str) -> None:
    from polyswarm_modules.validators import invalid_url_reason

    reason = invalid_url_reason(url) or ""

    assert "secret" not in reason
    assert "user" not in reason
    assert "example.com" in reason
