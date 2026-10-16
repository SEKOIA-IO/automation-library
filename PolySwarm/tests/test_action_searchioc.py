from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import requests
from polyswarm_api import exceptions as ps_exceptions

from polyswarm_modules import PolyswarmModule
from polyswarm_modules.action_polyswarm_searchioc import SearchIoc
from tests.helpers import autospec_build_client

MODULE_PATH = "polyswarm_modules.action_polyswarm_searchioc"


@pytest.fixture
def action(data_storage: str, module: PolyswarmModule) -> SearchIoc:
    return SearchIoc(module=module, data_path=data_storage)


def _make_item(
    *,
    sha256: str = "aa" * 32,
    sha1: str = "bb" * 20,
    md5: str = "cc" * 16,
    malicious: int = 4,
    benign: int = 1,
    total_detections: int = 5,
    polyscore: float = 0.91,
    family: str = "Emotet",
    tags: list[str] | None = None,
) -> SimpleNamespace:
    document: dict[str, Any] = {
        "artifact": {"sha256": sha256, "sha1": sha1, "md5": md5},
        "scan": {
            "latest_scan": {"polyscore": polyscore, "created": "2026-02-01T00:00:00Z"},
            "detections": {"malicious": malicious, "benign": benign, "total": total_detections},
            "first_scan": {"created": "2026-01-01T00:00:00Z"},
            "mimetype": {"mime": "application/x-dosexec"},
            "filename": ["dropper.exe"],
        },
        "polyunite": {"malware_family": family} if family else {},
        "tags": tags if tags is not None else [],
    }
    return SimpleNamespace(json=document)


# --- exactly one of ip/domain/ttp/imphash ---


def test_no_indicator_is_refused_without_an_api_call(action: SearchIoc) -> None:
    with patch(f"{MODULE_PATH}.build_client", new_callable=autospec_build_client) as mock_build_client:
        response = action.run({})

    assert response is None
    mock_build_client.assert_not_called()
    assert "exactly one" in action.error_message.lower()


def test_all_blank_indicators_are_treated_as_none_supplied(action: SearchIoc) -> None:
    with patch(f"{MODULE_PATH}.build_client", new_callable=autospec_build_client) as mock_build_client:
        response = action.run({"ip": "", "domain": "   ", "ttp": None, "imphash": ""})

    assert response is None
    mock_build_client.assert_not_called()
    assert "exactly one" in action.error_message.lower()


def test_two_indicators_supplied_together_is_refused_without_an_api_call(action: SearchIoc) -> None:
    with patch(f"{MODULE_PATH}.build_client", new_callable=autospec_build_client) as mock_build_client:
        response = action.run({"ip": "8.8.8.8", "domain": "example.com"})

    assert response is None
    mock_build_client.assert_not_called()
    assert "domain" in action.error_message.lower()
    assert "ip" in action.error_message.lower()


def test_all_four_indicators_supplied_together_is_refused(action: SearchIoc) -> None:
    with patch(f"{MODULE_PATH}.build_client", new_callable=autospec_build_client) as mock_build_client:
        response = action.run({"ip": "8.8.8.8", "domain": "example.com", "ttp": "T1059", "imphash": "d" * 32})

    assert response is None
    mock_build_client.assert_not_called()


# --- IP refusal, same wording family as action_polyswarm_scanip.py ---


@pytest.mark.parametrize(
    "ip,fragment",
    [
        ("127.0.0.1", "loopback"),
        ("169.254.1.1", "link-local"),
        ("10.0.0.5", "private"),
        # 240.0.0.1 is reserved space; Python's ipaddress also flags it
        # private, and _invalid_ip_reason checks private before reserved, so
        # it is refused with the private wording rather than the reserved one.
        ("240.0.0.1", "private"),
    ],
)
def test_disallowed_ip_kinds_are_refused_without_an_api_call(action: SearchIoc, ip: str, fragment: str) -> None:
    with patch(f"{MODULE_PATH}.build_client", new_callable=autospec_build_client) as mock_build_client:
        response = action.run({"ip": ip})

    assert response is None
    mock_build_client.assert_not_called()
    assert fragment in action.error_message.lower()


def test_malformed_ip_is_refused_without_an_api_call(action: SearchIoc) -> None:
    with patch(f"{MODULE_PATH}.build_client", new_callable=autospec_build_client) as mock_build_client:
        response = action.run({"ip": "not-an-ip"})

    assert response is None
    mock_build_client.assert_not_called()
    assert "not a valid ip" in action.error_message.lower()


@pytest.mark.parametrize(
    "imphash",
    [
        "d41d8cd98f00b204e9800998ecf8427",  # 31 characters
        "d41d8cd98f00b204e9800998ecf8427e0",  # 33 characters
        "z41d8cd98f00b204e9800998ecf8427e",  # not hexadecimal
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",  # a SHA256, not an imphash
    ],
)
def test_malformed_imphash_is_refused_without_an_api_call(action: SearchIoc, imphash: str) -> None:
    with patch(f"{MODULE_PATH}.build_client", new_callable=autospec_build_client) as mock_build_client:
        response = action.run({"imphash": imphash})

    assert response is None
    mock_build_client.assert_not_called()
    assert "not a plausible imphash" in action.error_message.lower()


# --- each indicator type reaches the client as exactly one keyword argument ---


@patch(f"{MODULE_PATH}.build_client", new_callable=autospec_build_client)
def test_public_ip_calls_the_client_with_only_ip(mock_build_client: MagicMock, action: SearchIoc) -> None:
    mock_build_client.return_value.search_by_ioc.return_value = iter([])

    action.run({"ip": "8.8.8.8"})

    mock_build_client.return_value.search_by_ioc.assert_called_once_with(ip="8.8.8.8")


@patch(f"{MODULE_PATH}.build_client", new_callable=autospec_build_client)
def test_domain_calls_the_client_with_only_domain(mock_build_client: MagicMock, action: SearchIoc) -> None:
    mock_build_client.return_value.search_by_ioc.return_value = iter([])

    action.run({"domain": "evil.example.com"})

    mock_build_client.return_value.search_by_ioc.assert_called_once_with(domain="evil.example.com")


@patch(f"{MODULE_PATH}.build_client", new_callable=autospec_build_client)
def test_ttp_calls_the_client_with_only_ttp(mock_build_client: MagicMock, action: SearchIoc) -> None:
    mock_build_client.return_value.search_by_ioc.return_value = iter([])

    action.run({"ttp": "T1059.001"})

    mock_build_client.return_value.search_by_ioc.assert_called_once_with(ttp="T1059.001")


@patch(f"{MODULE_PATH}.build_client", new_callable=autospec_build_client)
def test_imphash_calls_the_client_with_only_imphash(mock_build_client: MagicMock, action: SearchIoc) -> None:
    mock_build_client.return_value.search_by_ioc.return_value = iter([])

    action.run({"imphash": "d41d8cd98f00b204e9800998ecf8427e"})

    mock_build_client.return_value.search_by_ioc.assert_called_once_with(imphash="d41d8cd98f00b204e9800998ecf8427e")


# --- found / not found branches ---


@patch(f"{MODULE_PATH}.build_client", new_callable=autospec_build_client)
def test_a_hit_activates_the_found_branch(mock_build_client: MagicMock, action: SearchIoc) -> None:
    mock_build_client.return_value.search_by_ioc.return_value = iter([_make_item()])

    response = action.run({"domain": "evil.example.com"})
    assert response is not None

    assert action._outputs == {"found": True}
    assert response["found"] is True
    assert response["indicator_type"] == "domain"
    assert response["indicator"] == "evil.example.com"
    assert response["returned_count"] == 1
    result = response["results"][0]
    assert result["sha256"] == "aa" * 32
    assert result["malicious_detections"] == 4
    assert result["benign_detections"] == 1
    assert result["polyscore"] == 0.91
    assert result["family"] == "Emotet"
    assert result["permalink"].endswith("aa" * 32)
    assert result["mimetype"] == "application/x-dosexec"
    assert result["filenames"] == ["dropper.exe"]


@patch(f"{MODULE_PATH}.build_client", new_callable=autospec_build_client)
def test_no_hits_activates_the_not_found_branch(mock_build_client: MagicMock, action: SearchIoc) -> None:
    mock_build_client.return_value.search_by_ioc.return_value = iter([])

    response = action.run({"imphash": "d" * 32})
    assert response is not None

    assert action._outputs == {"not found": True}
    assert response["found"] is False
    assert response["results"] == []
    assert response["returned_count"] == 0


@patch(f"{MODULE_PATH}.build_client", new_callable=autospec_build_client)
def test_a_204_style_exception_is_treated_as_not_found_not_an_error(
    mock_build_client: MagicMock, action: SearchIoc
) -> None:
    mock_build_client.return_value.search_by_ioc.side_effect = ps_exceptions.NotFoundException(MagicMock(), "404")

    response = action.run({"ttp": "T1059"})

    assert response is not None
    assert response["found"] is False
    assert action.error_message is None
    assert action._outputs == {"not found": True}


@patch(f"{MODULE_PATH}.build_client", new_callable=autospec_build_client)
def test_multiple_hits_are_all_returned(mock_build_client: MagicMock, action: SearchIoc) -> None:
    items = [_make_item(sha256=f"{i:02x}" * 32) for i in range(1, 4)]
    mock_build_client.return_value.search_by_ioc.return_value = iter(items)

    response = action.run({"domain": "evil.example.com"})
    assert response is not None

    assert response["returned_count"] == 3
    assert len(response["results"]) == 3


# --- exception handling never leaks the client's own message ---


@patch(f"{MODULE_PATH}.build_client", new_callable=autospec_build_client)
def test_invalid_indicator_error_does_not_quote_the_client_exception(
    mock_build_client: MagicMock, action: SearchIoc
) -> None:
    secret_bearing_message = "GET /ioc/search?apikey=SECRET&domain=evil.example.com"
    mock_build_client.return_value.search_by_ioc.side_effect = ps_exceptions.InvalidValueException(
        secret_bearing_message
    )

    response = action.run({"domain": "evil.example.com"})

    assert response is None
    assert "SECRET" not in action.error_message
    assert secret_bearing_message not in action.error_message


@patch(f"{MODULE_PATH}.build_client", new_callable=autospec_build_client)
def test_generic_polyswarm_failure_does_not_quote_the_client_exception(
    mock_build_client: MagicMock, action: SearchIoc
) -> None:
    secret_bearing_message = "request failed with headers Authorization: Bearer SECRET"
    mock_build_client.return_value.search_by_ioc.side_effect = ps_exceptions.PolyswarmAPIException(
        secret_bearing_message
    )

    response = action.run({"ttp": "T1059"})

    assert response is None
    assert "SECRET" not in action.error_message
    assert secret_bearing_message not in action.error_message


# --- field shape, missing data fails safe rather than raising ---


@patch(f"{MODULE_PATH}.build_client", new_callable=autospec_build_client)
def test_a_document_missing_family_and_tags_still_returns_a_result(
    mock_build_client: MagicMock, action: SearchIoc
) -> None:
    item = _make_item(family="", tags=[])
    mock_build_client.return_value.search_by_ioc.return_value = iter([item])

    response = action.run({"domain": "evil.example.com"})
    assert response is not None

    result = response["results"][0]
    assert result["family"] == ""
    assert result["tags"] == []
    assert result["families"] == []


@patch(f"{MODULE_PATH}.build_client", new_callable=autospec_build_client)
def test_an_item_with_no_readable_json_still_returns_a_row_with_blank_fields(
    mock_build_client: MagicMock, action: SearchIoc
) -> None:
    """A response shape this action did not anticipate fails safe, not with a traceback."""
    mock_build_client.return_value.search_by_ioc.return_value = iter([SimpleNamespace()])

    response = action.run({"domain": "evil.example.com"})
    assert response is not None

    assert response["found"] is True
    result = response["results"][0]
    assert result["sha256"] == ""
    assert result["permalink"] == ""
    assert result["polyscore"] is None


# --- the pivot is bounded ---


@patch(f"{MODULE_PATH}.build_client", new_callable=autospec_build_client)
def test_a_pivot_with_more_hits_than_the_limit_is_truncated_and_stops_consuming(
    mock_build_client: MagicMock, action: SearchIoc
) -> None:
    consumed: list[int] = []

    def endless() -> Any:
        for i in range(1, 10_000):
            consumed.append(i)
            yield _make_item(sha256=f"{i % 255:02x}" * 32)

    mock_build_client.return_value.search_by_ioc.return_value = endless()

    response = action.run({"domain": "common.example.com", "limit": 3})
    assert response is not None

    assert response["returned_count"] == 3
    assert response["limit"] == 3
    assert response["truncated"] is True
    assert action._outputs == {"truncated": True}
    # One item past the limit proves there was more; nothing beyond it is read.
    assert len(consumed) == 4


@patch(f"{MODULE_PATH}.build_client", new_callable=autospec_build_client)
def test_a_pivot_that_fits_the_limit_is_not_truncated(mock_build_client: MagicMock, action: SearchIoc) -> None:
    mock_build_client.return_value.search_by_ioc.return_value = iter([_make_item(), _make_item(sha256="bb" * 32)])

    response = action.run({"domain": "evil.example.com", "limit": 2})
    assert response is not None

    assert response["truncated"] is False
    assert response["limit"] == 2
    assert action._outputs == {"found": True}


@patch(f"{MODULE_PATH}.build_client", new_callable=autospec_build_client)
def test_the_limit_defaults_when_not_supplied(mock_build_client: MagicMock, action: SearchIoc) -> None:
    mock_build_client.return_value.search_by_ioc.return_value = iter([_make_item()])

    response = action.run({"domain": "evil.example.com"})
    assert response is not None

    assert response["limit"] == 20


@pytest.mark.parametrize("limit", [0, 201])
def test_a_limit_outside_the_bounds_is_rejected(action: SearchIoc, limit: int) -> None:
    with pytest.raises(ValueError):
        action.run({"domain": "evil.example.com", "limit": limit})


# --- connection errors and statuses ---


@patch(f"{MODULE_PATH}.build_client", new_callable=autospec_build_client)
def test_a_connection_error_is_an_action_error_not_a_traceback(
    mock_build_client: MagicMock, action: SearchIoc
) -> None:
    mock_build_client.return_value.search_by_ioc.side_effect = requests.ConnectionError("https://x/?key=SECRET")

    response = action.run({"domain": "evil.example.com"})

    assert response is None
    assert "ConnectionError" in action.error_message
    assert "SECRET" not in action.error_message


@patch(f"{MODULE_PATH}.build_client", new_callable=autospec_build_client)
def test_the_http_status_is_reported_without_the_client_message(
    mock_build_client: MagicMock, action: SearchIoc
) -> None:
    exc = ps_exceptions.UsageLimitsExceededException(SimpleNamespace(status_code=429), "key=SECRET rate limited")
    mock_build_client.return_value.search_by_ioc.side_effect = exc

    response = action.run({"domain": "evil.example.com"})

    assert response is None
    assert "HTTP 429" in action.error_message
    assert "SECRET" not in action.error_message


@pytest.mark.parametrize("domain", ["8.8.8.8", "not a host", "nodots"])
def test_implausible_domain_is_refused_without_an_api_call(action: SearchIoc, domain: str) -> None:
    with patch(f"{MODULE_PATH}.build_client", new_callable=autospec_build_client) as mock_build_client:
        response = action.run({"domain": domain})

    assert response is None
    mock_build_client.assert_not_called()
    assert action.error_message.startswith("Refusing to search")


@patch(f"{MODULE_PATH}.build_client", new_callable=autospec_build_client)
def test_plausible_domain_reaches_the_client(mock_build_client: MagicMock, action: SearchIoc) -> None:
    mock_build_client.return_value.search_by_ioc.return_value = iter([_make_item()])

    response = action.run({"domain": "example.com"})

    assert response["found"] is True
    mock_build_client.return_value.search_by_ioc.assert_called_once_with(domain="example.com")


@pytest.mark.parametrize("scan_extra", [{"first_scan": None}, {"first_scan": {"created": None}}])
@patch(f"{MODULE_PATH}.build_client", new_callable=autospec_build_client)
def test_null_first_scan_is_an_empty_first_seen(
    mock_build_client: MagicMock, action: SearchIoc, scan_extra: dict[str, Any]
) -> None:
    item = _make_item()
    item.json["scan"].update(scan_extra)
    mock_build_client.return_value.search_by_ioc.return_value = iter([item])

    response = action.run({"ip": "8.8.8.8"})

    assert response["results"][0]["first_seen"] == ""
